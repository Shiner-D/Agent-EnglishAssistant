"""Embedding service - supports local SentenceTransformer or API-based (OpenAI-compatible)."""
from typing import List
import httpx
from loguru import logger
from app.core.config import settings


class EmbeddingService:
    def __init__(self):
        self._model = None

    @property
    def _use_api(self) -> bool:
        return bool(settings.EMBEDDING_API_KEY and settings.EMBEDDING_BASE_URL)

    def _load_local_model(self):
        if self._use_api:
            logger.info("Embedding API mode enabled, skipping local model load.")
            return
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local embedding model: {settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)

    def _embed_via_api(self, texts: List[str]) -> List[List[float]]:
        url = settings.EMBEDDING_BASE_URL.rstrip("/") + "/embeddings"
        headers = {"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"}
        payload = {"model": settings.EMBEDDING_MODEL, "input": texts}
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data]

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self._use_api:
            return self._embed_via_api(texts)
        model = self._load_local_model() or self._model
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.embed([text])[0]


embedding_service = EmbeddingService()
