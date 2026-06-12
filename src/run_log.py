import json
import os
from datetime import datetime, timezone

from dateutil import parser as dtparser

RUN_LOG_PATH = "public/run_log.jsonl"


def _age_days(published, now):
    """Age of an article in days, or None if the timestamp can't be parsed."""
    if not published:
        return None
    try:
        dt = dtparser.parse(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() / 86400
    except Exception:
        return None


def summarize_selection(items: list, fresh_days: int) -> dict:
    """Score/recency breakdown of the emitted items.

    `fresh_count` is how many emitted articles were published within
    `fresh_days` — a thin number here means the feed is recycling old
    articles rather than surfacing genuinely new ones.
    """
    now = datetime.now(timezone.utc)
    scores = [i["score"] for i in items if i.get("score") is not None]
    ages = sorted(
        a for a in (_age_days(i.get("published_at"), now) for i in items) if a is not None
    )
    return {
        "selected": len(items),
        "score_min": round(min(scores), 4) if scores else None,
        "score_max": round(max(scores), 4) if scores else None,
        "score_mean": round(sum(scores) / len(scores), 4) if scores else None,
        "fresh_days": fresh_days,
        "fresh_count": sum(1 for a in ages if a <= fresh_days),
        "age_days_median": round(ages[len(ages) // 2], 1) if ages else None,
        "age_days_max": round(ages[-1], 1) if ages else None,
    }


def record_run(stats: dict) -> dict:
    """Append one JSON line per run to RUN_LOG_PATH (committed to git history)."""
    stats = {"ts": datetime.now(timezone.utc).isoformat(), **stats}
    os.makedirs(os.path.dirname(RUN_LOG_PATH), exist_ok=True)
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False) + "\n")
    return stats
