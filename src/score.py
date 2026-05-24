import numpy as np
from datetime import datetime, timezone, timedelta
from src.config import TOP_K_SCORE, RECENCY_WEIGHT, RECENCY_DAYS
from src.store import get_all_raindrop_embeddings, get_conn, update_article_score


def _recency_weights(saved_ats: list[str]) -> np.ndarray:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENCY_DAYS)).isoformat()
    return np.array(
        [RECENCY_WEIGHT if s > cutoff else 1.0 for s in saved_ats],
        dtype=np.float32,
    )


def score_articles():
    raindrop_embs, saved_ats = get_all_raindrop_embeddings()
    if raindrop_embs.shape[0] == 0:
        print("WARNING: no raindrop embeddings found, skipping scoring")
        return

    weights = _recency_weights(saved_ats)
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
