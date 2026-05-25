import os

RAINDROP_TOKEN = os.environ.get("RAINDROP_TOKEN", "")
INOREADER_FEED_URL = os.environ.get("INOREADER_FEED_URL", "")

MODEL_NAME = "intfloat/multilingual-e5-small"
TOP_N = 30
TOP_K_SCORE = 10
RECENCY_DAYS = 90
SHORT_RECENCY_DAYS = 30
SHORT_RECENCY_WEIGHT = 2.0
MAX_CONTENT_CHARS = 5000
FETCH_TIMEOUT = 10
DEDUP_DAYS = 14
DB_PATH = "data/state.db"
RSS_OUTPUT = "public/custom.xml"
