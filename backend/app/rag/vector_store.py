"""ChromaDB vector store for word knowledge base."""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any
from loguru import logger
from app.core.config import settings
from app.rag.embedder import embedding_service


class VectorStore:
    def __init__(self):
        self._client = None
        self._collection = None

    def _get_client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PATH,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def get_collection(self):
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_documents(self, documents: List[Dict[str, Any]], batch_size: int = 500):
        collection = self.get_collection()
        total = len(documents)
        for i in range(0, total, batch_size):
            batch = documents[i: i + batch_size]
            ids = [str(doc["id"]) for doc in batch]
            texts = [doc["text"] for doc in batch]
            metadatas = [doc["metadata"] for doc in batch]
            embeddings = embedding_service.embed(texts)
            collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
            logger.info(f"Indexed {min(i + batch_size, total)}/{total} documents")

    def vector_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        collection = self.get_collection()
        query_embedding = embedding_service.embed_query(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        items = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            score = 1 - dist  # cosine similarity
            items.append({"text": doc, "metadata": meta, "score": score})
        return items

    def count(self) -> int:
        return self.get_collection().count()


vector_store = VectorStore()
