import os
import sqlite3
import numpy as np
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from src.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS raindrops (
    id         INTEGER PRIMARY KEY,
    url        TEXT NOT NULL,
    title      TEXT,
    excerpt    TEXT,
    saved_at   TEXT NOT NULL,
    embedding  BLOB,
    emb_model  TEXT,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS articles (
    url          TEXT PRIMARY KEY,
    title        TEXT,
    content      TEXT,
    published_at TEXT,
    embedding    BLOB,
    emb_model    TEXT,
    score        REAL,
    fetched_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS output_log (
    url        TEXT PRIMARY KEY,
    emitted_at TEXT NOT NULL,
    score      REAL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_raindrop_ids() -> set[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id FROM raindrops").fetchall()
    return {r["id"] for r in rows}


def insert_raindrops(items: list[dict]):
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO raindrops (id, url, title, excerpt, saved_at, fetched_at) "
            "VALUES (:id, :url, :title, :excerpt, :saved_at, :fetched_at)",
            items,
        )


def update_raindrop_embedding(raindrop_id: int, emb: np.ndarray, model: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE raindrops SET embedding=?, emb_model=? WHERE id=?",
            (emb.astype(np.float32).tobytes(), model, raindrop_id),
        )


def get_raindrops_without_embedding() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, url, title, excerpt, saved_at FROM raindrops WHERE embedding IS NULL"
        ).fetchall()


def get_recent_raindrop_embeddings(days: int) -> tuple[np.ndarray, list[str]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT embedding, saved_at FROM raindrops "
            "WHERE embedding IS NOT NULL AND saved_at > ?",
            (cutoff,),
        ).fetchall()
    if not rows:
        return np.empty((0, 384), dtype=np.float32), []
    embs = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    saved_ats = [r["saved_at"] for r in rows]
    return embs, saved_ats


def upsert_article(item: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO articles (url, title, content, published_at, fetched_at) "
            "VALUES (:url, :title, :content, :published_at, :fetched_at) "
            "ON CONFLICT(url) DO UPDATE SET "
            "title=excluded.title, content=excluded.content, "
            "published_at=excluded.published_at, fetched_at=excluded.fetched_at",
            item,
        )


def get_articles_without_embedding(expected_model: str | None = None) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if expected_model:
            return conn.execute(
                "SELECT url, title, content FROM articles "
                "WHERE embedding IS NULL OR emb_model IS NULL OR emb_model != ?",
                (expected_model,),
            ).fetchall()
        return conn.execute(
            "SELECT url, title, content FROM articles WHERE embedding IS NULL"
        ).fetchall()


def update_article_embedding(url: str, emb: np.ndarray, model: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET embedding=?, emb_model=? WHERE url=?",
            (emb.astype(np.float32).tobytes(), model, url),
        )


def update_article_score(url: str, score: float):
    with get_conn() as conn:
        conn.execute("UPDATE articles SET score=? WHERE url=?", (score, url))


def get_recent_emitted_urls(days: int) -> set[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url FROM output_log WHERE emitted_at > ?", (cutoff,)
        ).fetchall()
    return {r["url"] for r in rows}


def get_top_articles(n: int, exclude_urls: set[str]) -> list[sqlite3.Row]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, title, content, published_at, score FROM articles "
            "WHERE embedding IS NOT NULL AND score IS NOT NULL "
            "ORDER BY score DESC"
        ).fetchall()
    return [r for r in rows if r["url"] not in exclude_urls][:n]


def log_emissions(items: list[sqlite3.Row]):
    ts = now_iso()
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO output_log (url, emitted_at, score) VALUES (?, ?, ?)",
            [(r["url"], ts, r["score"]) for r in items],
        )


def cleanup_old_articles(days: int = 30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM articles WHERE fetched_at < ?", (cutoff,))
