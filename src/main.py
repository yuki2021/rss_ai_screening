from src.store import init_db, get_recent_emitted_urls, get_top_articles, log_emissions, cleanup_old_articles
from src.raindrop import fetch_all_raindrops
from src.feed_fetch import fetch_feed
from src.extract import extract_articles
from src.embed import embed_pending
from src.score import score_articles
from src.rss_gen import generate_rss
from src.config import TOP_N, DEDUP_DAYS


def main():
    print("Initializing DB...")
    init_db()

    print("Syncing Raindrop bookmarks...")
    new_raindrops = fetch_all_raindrops()
    print(f"  {new_raindrops} new raindrops")

    print("Fetching Inoreader feed...")
    new_articles = fetch_feed()
    print(f"  {new_articles} articles fetched")

    print("Extracting full text...")
    extract_articles()

    print("Computing embeddings...")
    embed_pending()

    print("Scoring articles...")
    score_articles()

    print(f"Selecting top {TOP_N} articles...")
    exclude = get_recent_emitted_urls(DEDUP_DAYS)
    top_items = get_top_articles(TOP_N, exclude)
    if not top_items:
        print("No articles to emit, keeping previous RSS.")
        return

    print(f"  selected {len(top_items)} articles")
    generate_rss([dict(r) for r in top_items])
    log_emissions(top_items)

    print("Cleaning up old articles...")
    cleanup_old_articles()

    print("Done.")


if __name__ == "__main__":
    main()
