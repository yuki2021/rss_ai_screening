import os

RAINDROP_TOKEN = os.environ.get("RAINDROP_TOKEN", "")
INOREADER_FEED_URL = os.environ.get("INOREADER_FEED_URL", "")

MODEL_NAME = "intfloat/multilingual-e5-small"
EMB_ARTICLE_TAG = MODEL_NAME + "+qp"
TOP_N = 30
RECENCY_DAYS = 365  # raindrops older than this drop out of the taste profile
# A raindrop's similarity is reduced by up to PREF_MAX_PENALTY as it ages,
# half of that after PREF_HALF_LIFE_DAYS — so a fresh interest outranks one
# bookmarked a year ago at the same similarity.
PREF_HALF_LIFE_DAYS = 90
PREF_MAX_PENALTY = 0.03
# URL prefixes (scheme stripped) that are neither part of the taste profile
# nor ever emitted, e.g. an author whose posts were bookmarked by mistake.
BLOCKED_URL_PREFIXES = (
    "qiita.com/maskot1977/",
)
RAINDROP_FULL_SYNC_DAYS = 7  # re-read every bookmark this often to catch deletions
MAX_CONTENT_CHARS = 5000
FETCH_TIMEOUT = 10
DEDUP_DAYS = 14
FRESH_DAYS = 3  # emitted articles newer than this count as "fresh" in run_log
HALF_LIFE_DAYS = 7  # article score halves every N days of age (recency decay)
DUPLICATE_SCORE_THRESHOLD = 0.95
DB_PATH = "data/state.db"
RSS_OUTPUT = "public/custom.xml"
