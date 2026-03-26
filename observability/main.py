"""FastAPI application entry point for Observability & Logging."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from observability import __version__
from observability.config import get_settings
from observability.database import init_db, get_db_session
from observability.routes import observability_router
from observability.services.alert_engine import AlertEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global alert task reference
_alert_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _alert_task

    # Startup
    logger.info("Starting Observability & Logging...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start background alert evaluation task
    async def run_alert_evaluator():
        logger.info("Starting alert evaluation loop")
        while True:
            try:
                async with get_db_session() as db:
                    engine = AlertEngine(db)
                    count = await engine.evaluate_rules()
                    if count > 0:
                        logger.info(f"Alert evaluator: created {count} alerts")
                    await asyncio.sleep(settings.alert_check_interval_seconds)
            except asyncio.CancelledError:
                logger.info("Alert evaluator cancelled")
                break
            except Exception as e:
                logger.error(f"Error in alert evaluator: {e}")
                await asyncio.sleep(5)

    _alert_task = asyncio.create_task(run_alert_evaluator())
    logger.info("Alert evaluator started")

    logger.info("Observability & Logging started")

    yield

    # Shutdown
    logger.info("Shutting down Observability & Logging...")

    if _alert_task:
        _alert_task.cancel()
        try:
            await _alert_task
        except asyncio.CancelledError:
            pass

    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Logging, metrics, distributed tracing, and alerting platform",
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

    from observability.schemas.tasks import ErrorDetail

    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json"),
    )


# Include routers
app.include_router(observability_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "observability.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
