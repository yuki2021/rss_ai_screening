import time
import httpx
from src.config import RAINDROP_TOKEN
from src.store import get_raindrop_ids, insert_raindrops, now_iso

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 6
REQUEST_INTERVAL = 0.6  # 100 req/min (limit: 120/min)


def _get_with_retry(client: httpx.Client, url: str, params: dict) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            wait = 2 ** (attempt + 2)
            print(f"  Timeout on attempt {attempt + 1}, retrying in {wait:.0f}s... ({exc})")
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


def fetch_all_raindrops() -> int:
    existing = get_raindrop_ids()
    headers = {"Authorization": f"Bearer {RAINDROP_TOKEN}"}
    page = 0
    per_page = 50
    total_new = 0

    with httpx.Client(headers=headers, timeout=30) as client:
        while True:
            resp = _get_with_retry(
                client,
                "https://api.raindrop.io/rest/v1/raindrops/0",
                params={"page": page, "perpage": per_page},
            )
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            new_items = []
            for item in items:
                rid = item["_id"]
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

            if len(items) < per_page:
                break
            page += 1
            time.sleep(REQUEST_INTERVAL)

    return total_new
