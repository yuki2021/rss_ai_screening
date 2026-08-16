import re
from html.parser import HTMLParser

import feedparser
from src.config import INOREADER_FEED_URL, MAX_CONTENT_CHARS
from src.store import upsert_article, now_iso

# Tags whose boundaries are word breaks in the rendered text.
_BLOCK_TAGS = {"br", "p", "div", "li", "tr", "blockquote", "cite", "h1", "h2", "h3"}


class _TagStripper(HTMLParser):
    """Collapse an HTML fragment down to its visible text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in _BLOCK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._parts)).strip()


def strip_html(fragment: str) -> str:
    """Reduce an RSS summary to plain text.

    Inoreader ships summaries as HTML, so the raw field is mostly markup and
    asset URLs. Embedding that instead of prose both inflates the length checks
    downstream and pollutes the vector.
    """
    if not fragment:
        return ""
    parser = _TagStripper()
    try:
        parser.feed(fragment)
        parser.close()
    except Exception:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()
    return parser.text()


def fetch_feed() -> int:
    url = INOREADER_FEED_URL + ("&" if "?" in INOREADER_FEED_URL else "?") + "n=1000"
    feed = feedparser.parse(url)
    count = 0
    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue
        content = strip_html(
            entry.get("summary", "")
            or entry.get("description", "")
            or ""
        )
        published = entry.get("published", entry.get("updated", now_iso()))
        upsert_article({
            "url": url,
            "title": entry.get("title", ""),
            "content": content[:MAX_CONTENT_CHARS],
            "published_at": published,
            "fetched_at": now_iso(),
        })
        count += 1
    return count
