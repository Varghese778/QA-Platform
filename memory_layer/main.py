"""FastAPI application entry point for Memory Layer."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from memory_layer import __version__
from memory_layer.config import get_settings
from memory_layer.database import init_db
from memory_layer.routes import memory_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Memory Layer...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    logger.info("Memory Layer started")

    yield

    # Shutdown
    logger.info("Shutting down Memory Layer...")
    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Project-scoped knowledge store with semantic search and knowledge graph",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    from datetime import datetime, timezone

    from memory_layer.schemas.tasks import ErrorDetail

    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json"),
    )


# Include routers
app.include_router(memory_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "memory_layer.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
