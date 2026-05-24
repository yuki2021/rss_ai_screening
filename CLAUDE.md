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

This is a single-pipeline CLI tool that runs on a schedule (JST 06:00 and 18:00 via GitHub Actions), filters RSS articles by personal interest, and publishes the result as `public/custom.xml` to GitHub Pages.

**Pipeline stages in `src/main.py`:**

1. **`raindrop.py`** — Fetches all Raindrop.io bookmarks via REST API (paginated, rate-limited at 100 req/min). New bookmarks are inserted into `raindrops` table. These bookmarks represent the user's taste profile.

2. **`feed_fetch.py`** — Parses an Inoreader RSS feed with `feedparser` and upserts entries into the `articles` table.

3. **`extract.py`** — For articles with short content (<200 chars), fetches the full page with `trafilatura` to get the actual article text (up to `MAX_CONTENT_CHARS`).

4. **`embed.py`** — Computes sentence embeddings for both raindrops (taste profile) and articles using `intfloat/multilingual-e5-small` via `sentence-transformers`. Embeddings are stored as raw `float32` bytes in SQLite BLOBs. Both raindrops and articles use the `"passage: "` prefix per E5 convention.

5. **`score.py`** — Scores each article by cosine similarity to the top-K raindrop embeddings. Recent raindrops (within `RECENCY_DAYS`) are weighted higher (`RECENCY_WEIGHT`). Since embeddings are L2-normalized, similarity is computed as a dot product.

6. **`rss_gen.py`** — Selects the top `TOP_N` articles (excluding URLs emitted within `DEDUP_DAYS`), writes `public/custom.xml` using `feedgen`, and logs emitted URLs to `output_log`.

**Persistence (`src/store.py`):**

SQLite at `data/state.db` with three tables:
- `raindrops` — bookmark taste profile with embeddings
- `articles` — candidate articles with embeddings and scores
- `output_log` — deduplication log of previously emitted URLs

The DB is preserved across GitHub Actions runs via `actions/cache` with `restore-keys: state-db-` (always restores the latest).

**Tunable constants in `src/config.py`:**
- `TOP_N = 30` — articles per RSS output
- `TOP_K_SCORE = 10` — top-K raindrops used for scoring each article
- `RECENCY_WEIGHT = 2.0` / `RECENCY_DAYS = 90` — recency boost for taste profile
- `DEDUP_DAYS = 14` — deduplication window
