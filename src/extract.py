from copy import deepcopy

import trafilatura
from trafilatura.settings import DEFAULT_CONFIG

from src.config import FETCH_TIMEOUT, MAX_CONTENT_CHARS
from src.store import get_conn

# trafilatura 2.x dropped the `timeout` argument from fetch_url(); the download
# timeout can only be supplied through a config object.
_CONFIG = deepcopy(DEFAULT_CONFIG)
_CONFIG["DEFAULT"]["DOWNLOAD_TIMEOUT"] = str(FETCH_TIMEOUT)


def extract_articles():
    """Fetch full text for articles that only have a short RSS summary."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, content FROM articles WHERE embedding IS NULL"
        ).fetchall()

    attempted = 0
    updated = 0
    for row in rows:
        url = row["url"]
        existing = row["content"] or ""
        if len(existing) >= 200:
            continue
        attempted += 1
        try:
            downloaded = trafilatura.fetch_url(url, config=_CONFIG)
            if not downloaded:
                print(f"  [extract] download failed: {url}")
                continue
            text = trafilatura.extract(downloaded, include_comments=False)
            if not text:
                print(f"  [extract] no main text found: {url}")
                continue
            with get_conn() as conn:
                conn.execute(
                    "UPDATE articles SET content=? WHERE url=?",
                    (text[:MAX_CONTENT_CHARS], url),
                )
            updated += 1
        except Exception as exc:
            print(f"  [extract] error on {url}: {type(exc).__name__}: {exc}")

    print(f"  {updated}/{attempted} articles updated with full text")
