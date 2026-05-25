import numpy as np
from datetime import datetime, timezone, timedelta
from src.config import TOP_K_SCORE, RECENCY_DAYS, MID_RECENCY_DAYS, MID_RECENCY_WEIGHT, SHORT_RECENCY_DAYS, SHORT_RECENCY_WEIGHT
from src.store import get_recent_raindrop_embeddings, get_conn, update_article_score


def _recency_weights(saved_ats: list[str]) -> np.ndarray:
    short_cutoff = (datetime.now(timezone.utc) - timedelta(days=SHORT_RECENCY_DAYS)).isoformat()
    mid_cutoff = (datetime.now(timezone.utc) - timedelta(days=MID_RECENCY_DAYS)).isoformat()

    def _weight(s: str) -> float:
        if s > short_cutoff:
            return SHORT_RECENCY_WEIGHT
        if s > mid_cutoff:
            return MID_RECENCY_WEIGHT
        return 1.0

    return np.array([_weight(s) for s in saved_ats], dtype=np.float32)


def score_articles():
    raindrop_embs, saved_ats = get_recent_raindrop_embeddings(RECENCY_DAYS)
    if raindrop_embs.shape[0] == 0:
        print(f"WARNING: no raindrop embeddings within last {RECENCY_DAYS} days, skipping scoring")
        return

    weights = _recency_weights(saved_ats)
    short_count = int((weights >= SHORT_RECENCY_WEIGHT).sum())
    mid_count = int(((weights >= MID_RECENCY_WEIGHT) & (weights < SHORT_RECENCY_WEIGHT)).sum())
    print(f"Scoring against {raindrop_embs.shape[0]} raindrops (last {RECENCY_DAYS} days): "
          f"{short_count} at {SHORT_RECENCY_WEIGHT}x, {mid_count} at {MID_RECENCY_WEIGHT}x, rest at 1.0x)")
    k = min(TOP_K_SCORE, raindrop_embs.shape[0])

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, embedding FROM articles WHERE embedding IS NOT NULL"
        ).fetchall()

    for row in rows:
        article_emb = np.frombuffer(row["embedding"], dtype=np.float32)
        # cosine similarity: both are L2-normalized, so dot product = cosine sim
        sims = raindrop_embs @ article_emb  # (N,)
        order = np.argsort(sims)[::-1][:k]
        top_sims = sims[order]
        top_weights = weights[order]
        score = float(np.average(top_sims, weights=top_weights))
        update_article_score(row["url"], score)
