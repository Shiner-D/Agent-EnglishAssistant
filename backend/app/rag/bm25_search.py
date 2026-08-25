"""BM25 keyword search for word knowledge base."""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from loguru import logger
from app.core.config import settings


class BM25Search:
    def __init__(self):
        self._bm25 = None
        self._corpus_metadata = []
        self._index_path = Path(settings.CHROMA_PATH).parent / "bm25_index.pkl"

    def build_index(self, documents: List[Dict[str, Any]]):
        tokenized = [doc["text"].lower().split() for doc in documents]
        self._corpus_metadata = [doc["metadata"] for doc in documents]
        self._corpus_texts = [doc["text"] for doc in documents]
        self._bm25 = BM25Okapi(tokenized)
        self._save_index()
        logger.info(f"BM25 index built with {len(documents)} documents")

    def _save_index(self):
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._index_path, "wb") as f:
            pickle.dump({
                "bm25": self._bm25,
                "metadata": self._corpus_metadata,
                "texts": self._corpus_texts,
            }, f)

    def load_index(self):
        if not self._index_path.exists():
            return False
        with open(self._index_path, "rb") as f:
            data = pickle.load(f)
        self._bm25 = data["bm25"]
        self._corpus_metadata = data["metadata"]
        self._corpus_texts = data["texts"]
        logger.info("BM25 index loaded from disk")
        return True

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if self._bm25 is None:
            if not self.load_index():
                return []
        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        max_score = max(scores[top_indices[0]], 1e-9) if top_indices else 1.0
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "text": self._corpus_texts[idx],
                    "metadata": self._corpus_metadata[idx],
                    "score": float(scores[idx]) / max_score,
                })
        return results


bm25_search = BM25Search()
