import trafilatura
from src.config import FETCH_TIMEOUT, MAX_CONTENT_CHARS
from src.store import get_conn


def extract_articles():
    """Fetch full text for articles that only have a short RSS summary."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, content FROM articles WHERE embedding IS NULL"
        ).fetchall()

    for row in rows:
        url = row["url"]
        existing = row["content"] or ""
        if len(existing) >= 200:
            continue
        try:
            downloaded = trafilatura.fetch_url(url, timeout=FETCH_TIMEOUT)
            if downloaded:
                text = trafilatura.extract(downloaded, include_comments=False)
                if text:
                    with get_conn() as conn:
                        conn.execute(
                            "UPDATE articles SET content=? WHERE url=?",
                            (text[:MAX_CONTENT_CHARS], url),
                        )
        except Exception:
            pass
