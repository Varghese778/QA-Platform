"""FastAPI application entry point for Orchestrator Service."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from orchestrator_service import __version__
from orchestrator_service.config import get_settings
from orchestrator_service.database import init_db, close_db
from orchestrator_service.routes import jobs_router, health_router
from orchestrator_service.services import TimeoutWatchdog, StateManager
from orchestrator_service.schemas import ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global watchdog instance
_watchdog: TimeoutWatchdog = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _watchdog

    # Startup
    logger.info("Starting Orchestrator Service...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start timeout watchdog
    # Note: In production, watchdog would use its own DB session
    # _watchdog = TimeoutWatchdog(db_session, state_manager)
    # await _watchdog.start()
    # logger.info("Timeout watchdog started")

    yield

    # Shutdown
    logger.info("Shutting down Orchestrator Service...")

    # Stop watchdog
    if _watchdog:
        await _watchdog.stop()

    # Close database
    await close_db()
    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Central coordination layer for the autonomous QA pipeline",
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
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json"),
    )


# Include routers
app.include_router(jobs_router)
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "orchestrator_service.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
