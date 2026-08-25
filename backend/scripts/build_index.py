"""
Build ChromaDB + BM25 index from cleaned word data.
Usage: python scripts/build_index.py --input data/words.json
"""
import json
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.vector_store import vector_store
from app.rag.bm25_search import bm25_search


def build_document(word_data: dict, idx: int) -> dict:
    parts = [word_data["word"]]
    if word_data.get("phonetic"):
        parts.append(word_data["phonetic"])
    if word_data.get("definition"):
        parts.append(word_data["definition"])
    if word_data.get("translation"):
        parts.append(word_data["translation"])
    if word_data.get("pos"):
        parts.append(word_data["pos"])
    text = " | ".join(parts)

    metadata = {
        "word": word_data["word"],
        "phonetic": word_data.get("phonetic") or "",
        "pos": word_data.get("pos") or "",
        "definition": word_data.get("definition") or "",
        "translation": word_data.get("translation") or "",
        "frequency": word_data.get("frequency", 0),
        "level": word_data.get("level") or "",
        "source": word_data.get("source", "ECDICT"),
    }
    return {"id": str(idx), "text": text, "metadata": metadata}


def main():
    parser = argparse.ArgumentParser(description="Build RAG indexes from words.json")
    parser.add_argument("--input", default="data/words.json", help="Path to words.json")
    parser.add_argument("--batch", type=int, default=500, help="Batch size for embedding")
    parser.add_argument("--min-freq", type=int, default=1, help="Minimum frequency (0 = all words)")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        words = json.load(f)

    if args.min_freq > 0:
        words = [w for w in words if w.get("frequency", 0) >= args.min_freq]

    print(f"Building index for {len(words)} words...")
    documents = [build_document(w, i) for i, w in enumerate(words)]

    print("Building vector index (ChromaDB)...")
    vector_store.add_documents(documents, batch_size=args.batch)

    print("Building BM25 index...")
    bm25_search.build_index(documents)

    print(f"Done. Total vectors in Chroma: {vector_store.count()}")


if __name__ == "__main__":
    main()
