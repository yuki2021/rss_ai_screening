import time
import httpx
from src.config import RAINDROP_TOKEN
from src.store import get_raindrop_ids, insert_raindrops, now_iso


def fetch_all_raindrops() -> int:
    existing = get_raindrop_ids()
    headers = {"Authorization": f"Bearer {RAINDROP_TOKEN}"}
    page = 0
    per_page = 50
    total_new = 0

    with httpx.Client(headers=headers, timeout=30) as client:
        while True:
            resp = client.get(
                "https://api.raindrop.io/rest/v1/raindrops/0",
                params={"page": page, "perpage": per_page},
            )
            resp.raise_for_status()
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
            time.sleep(0.2)

    return total_new
