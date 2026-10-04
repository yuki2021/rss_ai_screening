# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the full pipeline
uv run python -m src.main

# Run a single module (e.g. just scoring)
uv run python -c "from src.store import init_db; init_db(); from src.score import score_articles; score_articles()"
```

Required environment variables:
- `RAINDROP_TOKEN` — Raindrop.io API bearer token
- `INOREADER_FEED_URL` — Inoreader RSS feed URL (treated as a secret)

## Architecture

This is a single-pipeline CLI tool that runs on a schedule (JST 06:00 and 15:00 via GitHub Actions), filters RSS articles by personal interest, and publishes the result as `public/custom.xml` to GitHub Pages.

**The weekday morning run has a second trigger outside this repository.** `podcast_auto_player`'s Cloudflare Worker dispatches `update.yml` at JST 06:05 on weekdays, because GitHub's own scheduler stopped keeping time in late August 2026 — this workflow ran 3, 6, and once 11 hours late — and `morning_podcast` downstream reads `custom.xml` at JST 06:35 to build the day's briefing. The JST 06:00 cron is kept for weekends, which the Worker does not cover. `update.yml` has a `concurrency` group so the two triggers cannot race on the `Commit RSS` push.

**Pipeline stages in `src/main.py`:**

1. **`raindrop.py`** — Syncs Raindrop.io bookmarks via REST API (newest-first, rate-limited at 100 req/min) into the `raindrops` table. These bookmarks represent the user's taste profile. Normally the walk stops at the first page with no new bookmarks; once every `RAINDROP_FULL_SYNC_DAYS`, on an afternoon (JST ≥ 12:00) run only, it re-reads all ~43k bookmarks (~10 min) and deletes the ones removed in Raindrop. The last full sync time lives in the `meta` table.

2. **`feed_fetch.py`** — Parses an Inoreader RSS feed with `feedparser` and upserts entries into the `articles` table.

3. **`extract.py`** — For articles with short content (<200 chars), fetches the full page with `trafilatura` to get the actual article text (up to `MAX_CONTENT_CHARS`).

4. **`embed.py`** — Computes sentence embeddings for both raindrops (taste profile) and articles using `intfloat/multilingual-e5-small` via `sentence-transformers`. Embeddings are stored as raw `float32` bytes in SQLite BLOBs. Raindrops use the `"passage: "` prefix and articles the `"query: "` prefix (E5 convention).

5. **`score.py`** — Scores each article by its best cosine similarity to the raindrops saved within `RECENCY_DAYS`, after subtracting an age penalty from each raindrop (up to `PREF_MAX_PENALTY`, half of it at `PREF_HALF_LIFE_DAYS`), then multiplies by the article's own age decay (`HALF_LIFE_DAYS`). Articles ≥ `DUPLICATE_SCORE_THRESHOLD` similar to a raindrop score 0. Since embeddings are L2-normalized, similarity is a dot product.

6. **`rss_gen.py`** — Selects the top `TOP_N` articles (excluding URLs emitted within `DEDUP_DAYS`, already bookmarked, or matching `BLOCKED_URL_PREFIXES`), writes `public/custom.xml` using `feedgen`, and logs emitted URLs to `output_log`.

**Persistence (`src/store.py`):**

SQLite at `data/state.db` with four tables:
- `raindrops` — bookmark taste profile with embeddings
- `articles` — candidate articles with embeddings and scores
- `output_log` — deduplication log of previously emitted URLs
- `meta` — key/value run state (e.g. last Raindrop full sync)

The DB is preserved across GitHub Actions runs via `actions/cache` with `restore-keys: state-db-` (always restores the latest).

**Tunable constants in `src/config.py`:**
- `TOP_N = 30` — articles per RSS output
- `RECENCY_DAYS = 365` — raindrops older than this leave the taste profile
- `PREF_MAX_PENALTY` / `PREF_HALF_LIFE_DAYS` — how much older raindrops are discounted
- `BLOCKED_URL_PREFIXES` — URL prefixes (scheme stripped) excluded from both the taste profile and the output; raindrops stay in Raindrop
- `DEDUP_DAYS = 14` — deduplication window
