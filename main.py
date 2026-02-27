"""Application entry point.

Starts the FastAPI server with structured logging and validated configuration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import Request

from src.utils.config import settings
from src.utils.logger import get_logger, setup_logging

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    """App startup/shutdown lifecycle.

    Add your startup logic here (load models, connect to databases, etc.).
    """
    from src.api.dependencies import init_services, shutdown_services

    logger.info("app_startup", env=settings.app_env)
    init_services()
    yield
    shutdown_services()
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    from src.api.routes import router
    from src.utils.errors import AppError

    app = FastAPI(
        title="Knowledge Hub",
        description="RAG application for document ingestion, chat, Q&A generation, interview prep, and summarization.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
    )

    # CORS middleware — open in debug, locked down otherwise
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health_check(request: Request) -> dict:  # noqa: ARG001
        return {
            "status": "ok",
            "env": settings.app_env,
            "version": "0.1.0",
        }

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            status_code=_error_code_to_status(exc.code),
            content=exc.to_dict(),
        )

    return app


def _error_code_to_status(code: str) -> int:
    """Map AppError codes to HTTP status codes."""
    mapping = {
        "VALIDATION_ERROR": 400,
        "NO_RELEVANT_CONTEXT": 400,
        "UNAUTHORIZED": 401,
        "NOT_FOUND": 404,
        "SOURCE_NOT_FOUND": 404,
        "FILE_NOT_FOUND": 404,
        "SESSION_NOT_FOUND": 404,
        "DUPLICATE_SOURCE": 409,
        "FILE_TOO_LARGE": 413,
        "UNSUPPORTED_FORMAT": 415,
        "RATE_LIMITED": 429,
    }
    return mapping.get(code, 500)


def main() -> None:
    """Initialize logging, validate config, and start the server."""
    setup_logging(
        level=settings.logging.level,
        fmt=settings.logging.format,
    )

    logger.info(
        "starting_server",
        env=settings.app_env,
        debug=settings.app_debug,
        host=settings.server.host,
        port=settings.server.port,
    )

    uvicorn.run(
        "main:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        reload=settings.server.reload,
    )


if __name__ == "__main__":
    main()
