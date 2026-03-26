"""FastAPI application entry point for Async Processing."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from async_processing import __version__
from async_processing.config import get_settings
from async_processing.database import init_db, get_db_context
from async_processing.routes import events_router, set_gateway
from async_processing.services.websocket_gateway import WebSocketGateway
from async_processing.services.consumer_worker import get_or_create_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global task references
_consumer_task = None
_gateway = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _consumer_task, _gateway

    # Startup
    logger.info("Starting Async Processing...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize WebSocket gateway
    async with get_db_context() as db:
        _gateway = WebSocketGateway(db)
        set_gateway(_gateway)
    logger.info("WebSocket gateway initialized")

    # Start consumer worker (background task)
    async def run_consumer():
        async with get_db_context() as db:
            worker = await get_or_create_worker(db, _gateway)
            await worker.run_consumer_loop()

    _consumer_task = asyncio.create_task(run_consumer())
    logger.info("Consumer worker started")

    logger.info("Async Processing started")

    yield

    # Shutdown
    logger.info("Shutting down Async Processing...")

    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass

    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Event ingestion, real-time updates, and message distribution",
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

    from async_processing.schemas.tasks import ErrorDetail

    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json"),
    )


# Include routers
app.include_router(events_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "async_processing.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
