import numpy as np
from src.config import DUPLICATE_SCORE_THRESHOLD, RECENCY_DAYS
from src.store import get_recent_raindrop_embeddings, get_conn, update_article_score


def score_articles():
    raindrop_embs, _ = get_recent_raindrop_embeddings(RECENCY_DAYS)
    if raindrop_embs.shape[0] == 0:
        print(f"WARNING: no raindrop embeddings within last {RECENCY_DAYS} days, skipping scoring")
        return

    print(f"Scoring against {raindrop_embs.shape[0]} raindrops (last {RECENCY_DAYS} days)")

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, embedding FROM articles WHERE embedding IS NOT NULL"
        ).fetchall()

    for row in rows:
        article_emb = np.frombuffer(row["embedding"], dtype=np.float32)
        # cosine similarity: both are L2-normalized, so dot product = cosine sim
        sims = raindrop_embs @ article_emb  # (N,)
        score = float(sims.max())
        if score >= DUPLICATE_SCORE_THRESHOLD:
            score = 0.0
        update_article_score(row["url"], score)
