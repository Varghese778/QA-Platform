"""FastAPI application entry point for Auth & Access Control service."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth_service import __version__
from auth_service.config import get_settings
from auth_service.database import init_db, close_db
from auth_service.services import get_redis, close_redis
from auth_service.routes import (
    auth_router,
    users_router,
    projects_router,
    invitations_router,
    internal_router,
)
from auth_service.schemas import HealthResponse, ErrorResponse

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
    logger.info("Starting Auth & Access Control service...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize Redis
    await get_redis()
    logger.info("Redis connection established")

    yield

    # Shutdown
    logger.info("Shutting down Auth & Access Control service...")
    await close_db()
    await close_redis()
    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Centralized identity, authentication, and authorization layer for the QA platform",
    lifespan=lifespan,
    docs_url="/auth/v1/docs",
    redoc_url="/auth/v1/redoc",
    openapi_url="/auth/v1/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            error_description="An unexpected error occurred",
        ).model_dump(),
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )


# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(invitations_router)
app.include_router(internal_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "auth_service.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
