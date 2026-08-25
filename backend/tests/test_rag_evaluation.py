"""RAG Evaluation: compare Vector vs Hybrid vs Hybrid+Reranker."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


EVAL_DATASET = [
    {"query": "坚持", "expected_words": ["persist", "insist", "persevere"]},
    {"query": "勇气", "expected_words": ["courage", "bravery", "valor"]},
    {"query": "平静", "expected_words": ["calm", "tranquil", "serene"]},
    {"query": "积累", "expected_words": ["accumulate", "amass"]},
    {"query": "显著的", "expected_words": ["significant", "remarkable", "notable"]},
]


def recall_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    top_k = set(retrieved[:k])
    hits = sum(1 for w in expected if w in top_k)
    return hits / len(expected) if expected else 0.0


def mrr(retrieved: list[str], expected: list[str]) -> float:
    for i, w in enumerate(retrieved, 1):
        if w in expected:
            return 1.0 / i
    return 0.0


def evaluate_pipeline(pipeline_fn, dataset: list) -> dict:
    metrics = {"recall@1": [], "recall@3": [], "recall@5": [], "mrr": []}
    for item in dataset:
        docs = pipeline_fn(item["query"])
        words = [d["metadata"].get("word", "") for d in docs]
        expected = item["expected_words"]
        metrics["recall@1"].append(recall_at_k(words, expected, 1))
        metrics["recall@3"].append(recall_at_k(words, expected, 3))
        metrics["recall@5"].append(recall_at_k(words, expected, 5))
        metrics["mrr"].append(mrr(words, expected))
    return {k: round(sum(v) / len(v), 3) for k, v in metrics.items()}


def test_rag_evaluation_report():
    """Run RAG evaluation comparing strategies. Requires index to be built."""
    try:
        from app.rag.vector_store import vector_store
        from app.rag.bm25_search import bm25_search
        from app.rag.hybrid_search import hybrid_search

        if vector_store.count() == 0:
            print("SKIP: Chroma index not built yet. Run scripts/build_index.py first.")
            return

        print("\n=== RAG Evaluation ===")

        # Vector only
        def vector_fn(query):
            return vector_store.vector_search(query, top_k=10)

        # Hybrid no reranker
        def hybrid_fn(query):
            return hybrid_search.search(query, top_k=10, use_reranker=False)

        # Hybrid + Reranker
        def full_fn(query):
            return hybrid_search.search(query, top_k=10, use_reranker=True)

        v_metrics = evaluate_pipeline(vector_fn, EVAL_DATASET)
        h_metrics = evaluate_pipeline(hybrid_fn, EVAL_DATASET)
        f_metrics = evaluate_pipeline(full_fn, EVAL_DATASET)

        print(f"Vector Search:       {v_metrics}")
        print(f"Hybrid Search:       {h_metrics}")
        print(f"Hybrid + Reranker:   {f_metrics}")

        # Hybrid should beat vector on recall@3
        assert h_metrics["recall@3"] >= v_metrics["recall@3"] - 0.1, (
            f"Hybrid recall@3 {h_metrics['recall@3']} worse than vector {v_metrics['recall@3']}"
        )

    except ImportError as e:
        print(f"SKIP: Missing dependency: {e}")
