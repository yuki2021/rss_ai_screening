import numpy as np
from datetime import datetime, timezone

from dateutil import parser as dtparser

from src.config import DUPLICATE_SCORE_THRESHOLD, HALF_LIFE_DAYS, RECENCY_DAYS
from src.store import get_recent_raindrop_embeddings, get_conn, update_article_score


def _recency_decay(published_at, fetched_at, now) -> float:
    """0.5 ** (age_days / HALF_LIFE_DAYS).

    Uses the article's published time (falling back to fetched time) so that
    relevant-but-stale articles rank below fresher ones, and stop dominating
    the feed once their dedup window expires.
    """
    ts = published_at or fetched_at
    if not ts:
        return 1.0
    try:
        dt = dtparser.parse(ts)
    except Exception:
        return 1.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - dt).total_seconds() / 86400)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def score_articles():
    raindrop_embs, _ = get_recent_raindrop_embeddings(RECENCY_DAYS)
    if raindrop_embs.shape[0] == 0:
        print(f"WARNING: no raindrop embeddings within last {RECENCY_DAYS} days, skipping scoring")
        return

    print(f"Scoring against {raindrop_embs.shape[0]} raindrops (last {RECENCY_DAYS} days)")

    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, embedding, published_at, fetched_at FROM articles WHERE embedding IS NOT NULL"
        ).fetchall()

    for row in rows:
        article_emb = np.frombuffer(row["embedding"], dtype=np.float32)
        # cosine similarity: both are L2-normalized, so dot product = cosine sim
        sims = raindrop_embs @ article_emb  # (N,)
        sim = float(sims.max())
        if sim >= DUPLICATE_SCORE_THRESHOLD:
            # near-identical to an existing raindrop — suppress as a duplicate
            score = 0.0
        else:
            score = sim * _recency_decay(row["published_at"], row["fetched_at"], now)
        update_article_score(row["url"], score)
