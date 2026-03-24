"""FastAPI application entry point for Artifact Storage."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from artifact_storage import __version__
from artifact_storage.config import get_settings
from artifact_storage.database import init_db
from artifact_storage.routes import artifacts_router
from artifact_storage.services.virus_scanner import VirusScanner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global scanner instance
_scanner_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _scanner_task

    # Startup
    logger.info("Starting Artifact Storage...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    logger.info("Artifact Storage started")

    yield

    # Shutdown
    logger.info("Shutting down Artifact Storage...")

    if _scanner_task:
        _scanner_task.cancel()
        try:
            await _scanner_task
        except asyncio.CancelledError:
            pass

    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Binary artifact storage and management with virus scanning",
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

    from artifact_storage.schemas.tasks import ErrorDetail

    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json"),
    )


# Include routers
app.include_router(artifacts_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "artifact_storage.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
