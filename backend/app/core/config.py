from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI English Tutor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/app.db"

    # Chroma
    CHROMA_PATH: str = str(BASE_DIR / "data" / "chroma")
    CHROMA_COLLECTION: str = "ecdict"

    # LLM - DeepSeek (OpenAI-compatible)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    # Embedding - use local BGE-M3 or API
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""

    # Reranker
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # RAG
    RETRIEVAL_TOP_K: int = 10
    RERANK_TOP_K: int = 5
    BM25_WEIGHT: float = 0.3
    VECTOR_WEIGHT: float = 0.7

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
