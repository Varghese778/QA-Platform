"""FastAPI application entry point for Multi-Agent Engine."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from multi_agent_engine import __version__
from multi_agent_engine.config import get_settings
from multi_agent_engine.routes import tasks_router
from multi_agent_engine.core.task_queue import get_redis, close_redis
from multi_agent_engine.core.agent_registry import AgentRegistry
from multi_agent_engine.core.scheduler import WorkStealingScheduler
from multi_agent_engine.schemas import ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global scheduler instance
_scheduler: WorkStealingScheduler = None
_agent_registry: AgentRegistry = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _scheduler, _agent_registry

    # Startup
    logger.info("Starting Multi-Agent Engine...")

    # Initialize Redis
    redis_client = await get_redis()
    logger.info("Redis connected")

    # Initialize agent registry
    from multi_agent_engine.core.task_queue import TaskQueueManager
    _agent_registry = AgentRegistry()
    queue_manager = TaskQueueManager(redis_client)

    # Initialize scheduler
    _scheduler = WorkStealingScheduler(queue_manager, _agent_registry)
    await _scheduler.start()
    await _agent_registry.start()

    # Register default agents (MVP: 2 agents per type)
    for task_type in ["PARSE_STORY", "CLASSIFY_DOMAIN", "FETCH_CONTEXT", "GENERATE_TESTS", "VALIDATE_TESTS", "ANALYSE_COVERAGE"]:
        from multi_agent_engine.schemas import TaskType
        task_enum = TaskType(task_type)
        for i in range(2):
            agent = _agent_registry.register_agent(task_enum)
            logger.info(f"Registered agent {agent.agent_id} ({task_type})")

    logger.info("Multi-Agent Engine started")

    yield

    # Shutdown
    logger.info("Shutting down Multi-Agent Engine...")

    if _scheduler:
        await _scheduler.stop()
    if _agent_registry:
        await _agent_registry.stop()

    await close_redis()
    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Pool of specialised AI agents for autonomous QA test generation",
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
app.include_router(tasks_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "multi_agent_engine.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
