import os
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from src.config import RSS_OUTPUT


def generate_rss(items: list) -> None:
    fg = FeedGenerator()
    fg.id("https://yuki2021.github.io/rss_ai_screening/custom.xml")
    fg.title("RSS AI Screening — Personalized")
    fg.link(href="https://yuki2021.github.io/rss_ai_screening/custom.xml", rel="self")
    fg.description("AI-filtered RSS feed based on Raindrop.io preferences")
    fg.language("ja")
    fg.updated(datetime.now(timezone.utc))

    for item in items:
        fe = fg.add_entry()
        fe.id(item["url"])
        fe.title(item["title"] or "(no title)")
        fe.link(href=item["url"])
        score_str = f"{item['score']:.3f}" if item.get("score") is not None else "N/A"
        fe.description(f"[score: {score_str}] {(item.get('content') or '')[:300]}")
        published = item.get("published_at")
        if published:
            try:
                from dateutil import parser as dtparser
                dt = dtparser.parse(published)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                fe.published(dt)
            except Exception:
                fe.published(datetime.now(timezone.utc))
        else:
            fe.published(datetime.now(timezone.utc))

    os.makedirs(os.path.dirname(RSS_OUTPUT), exist_ok=True)
    fg.rss_file(RSS_OUTPUT)
