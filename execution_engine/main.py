"""FastAPI application entry point for Execution Engine."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from execution_engine import __version__
from execution_engine.config import get_settings
from execution_engine.database import init_db
from execution_engine.routes import executions_router

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
    logger.info("Starting Execution Engine...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    logger.info("Execution Engine started")

    yield

    # Shutdown
    logger.info("Shutting down Execution Engine...")
    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Test execution engine with result reporting and flaky detection",
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

    from execution_engine.schemas.tasks import ErrorDetail

    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json"),
    )


# Include routers
app.include_router(executions_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "execution_engine.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
