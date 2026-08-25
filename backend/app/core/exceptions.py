"""Global exception handlers."""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
import httpx


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


async def llm_timeout_handler(request: Request, exc: httpx.TimeoutException):
    logger.warning(f"LLM timeout on {request.url}")
    return JSONResponse(
        status_code=504,
        content={"detail": "AI service timeout. Please retry."},
    )
