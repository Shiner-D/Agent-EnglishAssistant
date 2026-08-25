from contextlib import asynccontextmanager
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import httpx

from app.core.config import settings
from app.core.exceptions import http_exception_handler, general_exception_handler, llm_timeout_handler
from app.models.database import init_db, engine
from app.api import chat, users, words, exercises, tts, dashboard, stt
from app.rag.embedder import embedding_service
from app.rag.reranker import reranker


async def _migrate_db():
    """Add new columns to existing tables (idempotent)."""
    async with engine.begin() as conn:
        try:
            await conn.execute(__import__('sqlalchemy').text(
                "ALTER TABLE messages ADD COLUMN sources JSON"
            ))
            logger.info("Migration: added messages.sources column.")
        except Exception:
            pass  # column already exists


def setup_logging():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    logger.add(
        "data/app.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time} | {level} | {name} | {message}",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting up AI English Tutor...")
    await init_db()
    await _migrate_db()
    logger.info("Database initialized.")
    if embedding_service._use_api:
        logger.info(f"Embedding: API mode ({settings.EMBEDDING_BASE_URL}, model={settings.EMBEDDING_MODEL})")
    else:
        logger.info("Pre-loading local embedding model (this may take a moment on first run)...")
        embedding_service._load_local_model()
    if reranker._enabled:
        logger.info("Pre-loading reranker model (this may take a moment on first run)...")
        reranker._load_model()
    else:
        logger.info("Reranker: disabled.")
    logger.info("Server ready.")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(httpx.TimeoutException, llm_timeout_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(words.router, prefix="/api/words", tags=["Words"])
app.include_router(exercises.router, prefix="/api/exercises", tags=["Exercises"])
app.include_router(tts.router, prefix="/api/tts", tags=["TTS"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(stt.router, prefix="/api/stt", tags=["STT"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
