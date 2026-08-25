"""BGE Reranker for second-stage ranking. Disabled when RERANKER_MODEL is empty."""
from typing import List, Dict, Any
from loguru import logger
from app.core.config import settings


class Reranker:
    def __init__(self):
        self._model = None

    @property
    def _enabled(self) -> bool:
        return bool(settings.RERANKER_MODEL)

    def _load_model(self):
        if not self._enabled:
            logger.info("Reranker disabled (RERANKER_MODEL is empty).")
            return
        if self._model is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {settings.RERANKER_MODEL}")
            self._model = CrossEncoder(settings.RERANKER_MODEL)

    def rerank(self, query: str, docs: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not docs:
            return []
        if not self._enabled or self._model is None:
            return docs[:top_k]
        pairs = [(query, doc["text"]) for doc in docs]
        scores = self._model.predict(pairs)
        for doc, score in zip(docs, scores):
            doc["rerank_score"] = float(score)
        ranked = sorted(docs, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]


reranker = Reranker()
