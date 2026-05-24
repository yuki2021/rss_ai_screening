import feedparser
from src.config import INOREADER_FEED_URL
from src.store import upsert_article, now_iso


def fetch_feed() -> int:
    feed = feedparser.parse(INOREADER_FEED_URL)
    count = 0
    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue
        content = (
            entry.get("summary", "")
            or entry.get("description", "")
            or ""
        )
        published = entry.get("published", entry.get("updated", now_iso()))
        upsert_article({
            "url": url,
            "title": entry.get("title", ""),
            "content": content[:5000],
            "published_at": published,
            "fetched_at": now_iso(),
        })
        count += 1
    return count
