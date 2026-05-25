import numpy as np
from src.config import TOP_K_SCORE, RECENCY_DAYS
from src.store import get_recent_raindrop_embeddings, get_conn, update_article_score


def score_articles():
    raindrop_embs, saved_ats = get_recent_raindrop_embeddings(RECENCY_DAYS)
    if raindrop_embs.shape[0] == 0:
        print(f"WARNING: no raindrop embeddings within last {RECENCY_DAYS} days, skipping scoring")
        return

    print(f"Scoring against {raindrop_embs.shape[0]} recent raindrops (last {RECENCY_DAYS} days)")
    k = min(TOP_K_SCORE, raindrop_embs.shape[0])

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, embedding FROM articles WHERE embedding IS NOT NULL"
        ).fetchall()

    for row in rows:
        article_emb = np.frombuffer(row["embedding"], dtype=np.float32)
        # cosine similarity: both are L2-normalized, so dot product = cosine sim
        sims = raindrop_embs @ article_emb  # (N,)
        top_sims = np.sort(sims)[::-1][:k]
        score = float(np.mean(top_sims))
        update_article_score(row["url"], score)
