"""Hybrid Search = BM25 + Vector Search + optional Reranker."""
from typing import List, Dict, Any
from loguru import logger
from app.core.config import settings
from app.rag.vector_store import vector_store
from app.rag.bm25_search import bm25_search
from app.rag.reranker import reranker


class HybridSearchPipeline:
    def search(
        self,
        query: str,
        top_k: int | None = None,
        use_reranker: bool = True,
    ) -> List[Dict[str, Any]]:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        rerank_k = settings.RERANK_TOP_K

        # Parallel retrieval
        vector_results = vector_store.vector_search(query, top_k=top_k)
        bm25_results = bm25_search.search(query, top_k=top_k)

        # Merge with RRF (Reciprocal Rank Fusion)
        merged = self._rrf_merge(vector_results, bm25_results, top_k=top_k)

        if use_reranker and merged:
            merged = reranker.rerank(query, merged, top_k=rerank_k)

        return merged

    def _rrf_merge(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        top_k: int,
        k: int = 60,
    ) -> List[Dict]:
        scores: Dict[str, float] = {}
        docs_map: Dict[str, Dict] = {}

        for rank, doc in enumerate(vector_results):
            key = doc["metadata"].get("word", doc["text"][:50])
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
            doc["source_type"] = "vector"
            doc["retrieval_score"] = doc.get("score", 0.0)
            docs_map[key] = doc

        for rank, doc in enumerate(bm25_results):
            key = doc["metadata"].get("word", doc["text"][:50])
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
            if key not in docs_map:
                doc["source_type"] = "bm25"
                doc["retrieval_score"] = doc.get("score", 0.0)
                docs_map[key] = doc
            else:
                # Already exists from vector — update score
                docs_map[key]["source_type"] = "hybrid"

        ranked_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]
        results = []
        for key in ranked_keys:
            doc = docs_map[key]
            doc["rrf_score"] = scores[key]
            results.append(doc)
        return results


hybrid_search = HybridSearchPipeline()
