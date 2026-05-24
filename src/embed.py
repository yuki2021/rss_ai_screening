import numpy as np
from sentence_transformers import SentenceTransformer
from src.config import MODEL_NAME
from src.store import (
    get_raindrops_without_embedding,
    update_raindrop_embedding,
    get_articles_without_embedding,
    update_article_embedding,
)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _text_for_raindrop(row) -> str:
    parts = []
    if row["title"]:
        parts.append(row["title"])
    if row["excerpt"]:
        parts.append(row["excerpt"])
    return "passage: " + " ".join(parts) if parts else "passage: (no content)"


def _text_for_article(row) -> str:
    parts = []
    if row["title"]:
        parts.append(row["title"])
    if row["content"]:
        parts.append(row["content"][:2000])
    return "passage: " + " ".join(parts) if parts else "passage: (no content)"


def embed_pending():
    model = get_model()

    raindrop_rows = get_raindrops_without_embedding()
    if raindrop_rows:
        texts = [_text_for_raindrop(r) for r in raindrop_rows]
        embs = model.encode(
            texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False
        )
        for row, emb in zip(raindrop_rows, embs):
            update_raindrop_embedding(row["id"], emb, MODEL_NAME)

    article_rows = get_articles_without_embedding()
    if article_rows:
        texts = [_text_for_article(r) for r in article_rows]
        embs = model.encode(
            texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False
        )
        for row, emb in zip(article_rows, embs):
            update_article_embedding(row["url"], emb, MODEL_NAME)
