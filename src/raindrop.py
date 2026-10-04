import time
from datetime import datetime, timedelta, timezone

import httpx
from dateutil import parser as dtparser
from src.config import RAINDROP_TOKEN, RAINDROP_FULL_SYNC_DAYS
from src.store import (
    delete_raindrops,
    get_meta,
    get_raindrop_ids,
    insert_raindrops,
    now_iso,
    set_meta,
)

RETRY_STATUSES = {429, *range(500, 600)}
MAX_RETRIES = 6
REQUEST_INTERVAL = 0.6  # 100 req/min (limit: 120/min)
FULL_SYNC_META_KEY = "raindrop_full_sync_at"
# A full sync that would delete more than this share of stored bookmarks is
# assumed to be a bad listing, not real deletions.
MAX_DELETE_RATIO = 0.05
JST = timezone(timedelta(hours=9))


def _get_with_retry(client: httpx.Client, url: str, params: dict) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, params=params)
        except httpx.TransportError as exc:
            wait = 2 ** (attempt + 2)
            print(f"  Network error on attempt {attempt + 1}, retrying in {wait:.0f}s... ({exc})")
            if attempt + 1 == MAX_RETRIES:
                raise
            time.sleep(wait)
            continue
        if resp.status_code not in RETRY_STATUSES:
            resp.raise_for_status()
            return resp
        retry_after = resp.headers.get("Retry-After")
        wait = float(retry_after) if retry_after else 2 ** (attempt + 2)
        print(f"  HTTP {resp.status_code} on attempt {attempt + 1}, retrying in {wait:.0f}s...")
        time.sleep(wait)
    resp.raise_for_status()
    return resp


def _full_sync_due() -> bool:
    """A full re-read takes ~10 minutes for ~43k bookmarks, so keep it off the
    morning run that morning_podcast waits on (JST 06:35)."""
    if datetime.now(JST).hour < 12:
        return False
    last = get_meta(FULL_SYNC_META_KEY)
    if not last:
        return True
    return datetime.now(timezone.utc) - dtparser.parse(last) >= timedelta(
        days=RAINDROP_FULL_SYNC_DAYS
    )


def fetch_all_raindrops() -> int:
    """Insert bookmarks not yet stored.

    Pages are read newest-first, so normally the walk stops at the first page
    with nothing new. Every RAINDROP_FULL_SYNC_DAYS a full walk also drops
    bookmarks that were deleted in Raindrop.
    """
    stored = get_raindrop_ids()
    existing = set(stored)
    full = _full_sync_due()
    seen: set[int] = set()
    headers = {"Authorization": f"Bearer {RAINDROP_TOKEN}"}
    page = 0
    per_page = 50
    total_new = 0
    if full:
        print("  full sync: reading every bookmark")

    with httpx.Client(headers=headers, timeout=30) as client:
        while True:
            resp = _get_with_retry(
                client,
                "https://api.raindrop.io/rest/v1/raindrops/0",
                params={"page": page, "perpage": per_page, "sort": "-created"},
            )
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            new_items = []
            for item in items:
                rid = item["_id"]
                seen.add(rid)
                if rid in existing:
                    continue
                new_items.append({
                    "id": rid,
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "excerpt": item.get("excerpt", ""),
                    "saved_at": item.get("created", now_iso()),
                    "fetched_at": now_iso(),
                })
                existing.add(rid)

            if new_items:
                insert_raindrops(new_items)
                total_new += len(new_items)

            if not full and not new_items:
                break
            if len(items) < per_page:
                break
            page += 1
            time.sleep(REQUEST_INTERVAL)

    if full:
        gone = stored - seen
        if len(gone) > len(stored) * MAX_DELETE_RATIO:
            print(f"  WARNING: full sync would delete {len(gone)}/{len(stored)} bookmarks, skipping deletion")
        else:
            delete_raindrops(gone)
            print(f"  full sync: removed {len(gone)} bookmarks deleted in Raindrop")
            set_meta(FULL_SYNC_META_KEY, now_iso())

    return total_new
