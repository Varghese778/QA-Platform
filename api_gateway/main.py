"""FastAPI application entry point for API Gateway."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from api_gateway import __version__
from api_gateway.config import get_settings
from api_gateway.dependencies import get_jwt_validator, cleanup_dependencies
from api_gateway.core.rate_limiter import get_redis, close_redis
from api_gateway.core.proxy_client import close_proxy_client
from api_gateway.middleware import (
    RequestIDMiddleware,
    AccessLogMiddleware,
    SecurityHeadersMiddleware,
)
from api_gateway.routes import (
    health_router,
    jobs_router,
    projects_router,
    uploads_router,
    websocket_router,
    demo_router,
    integrations_router,
)
from api_gateway.schemas import ErrorEnvelope

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()





def run_demo_server():
    """Starts a simple HTTP server to host the demo app on port 5000."""
    import os
    import http.server
    import socketserver
    
    # Locate the demo_app directory
    # In container: /app/api_gateway/demo_app
    # In local: c:\Users\shari\OneDrive\Desktop\QA-Platform\api_gateway\demo_app
    possible_paths = [
        "/app/api_gateway/demo_app",
        "api_gateway/demo_app",
        "demo_app"
    ]
    demo_path = None
    for p in possible_paths:
        if os.path.exists(p):
            demo_path = p
            break
            
    if not demo_path:
        print(f"FAILED to start demo server: demo_app directory not found among {possible_paths}")
        return

    os.chdir(demo_path)
    handler = http.server.SimpleHTTPRequestHandler
    
    # Allow port reuse to avoid 'address already in use' errors on reload
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 5000), handler) as httpd:
        print(f"Serving demo app at http://localhost:5000 from {demo_path}")
        httpd.serve_forever()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    import threading
    threading.Thread(target=run_demo_server, daemon=True).start()
    
    logger.info("Starting API Gateway...")

    # Initialize JWT validator (fetches JWKS)
    # NOTE: We do NOT crash if JWKS is unavailable — auth-service may still be starting.
    # The JWT validator will lazy-initialize on first request via get_jwt_validator().
    try:
        jwt_validator = await get_jwt_validator()
        logger.info("JWT validator initialized")
    except Exception as e:
        logger.warning(
            f"JWT validator initialization deferred — auth-service may not be ready yet: {e}. "
            f"Will retry on first authenticated request."
        )

    # Initialize Redis connection
    try:
        await get_redis()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Rate limiting will fail open.")

    logger.info(f"API Gateway v{__version__} started successfully")

    yield

    # Shutdown
    logger.info("Shutting down API Gateway...")
    await cleanup_dependencies()
    logger.info("Cleanup complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Single ingress point for all client-originated traffic to the QA Platform",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add middleware (order matters - first added is outermost)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins_set),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors."""
    request_id = getattr(request.state, "request_id", "unknown")

    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "code": error["type"],
        })

    envelope = ErrorEnvelope(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details=errors,
        request_id=UUID(request_id) if request_id != "unknown" else UUID(int=0),
        timestamp=datetime.now(timezone.utc),
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=envelope.model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(f"Unhandled exception: {exc}")

    envelope = ErrorEnvelope(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        request_id=UUID(request_id) if request_id != "unknown" else UUID(int=0),
        timestamp=datetime.now(timezone.utc),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope.model_dump(mode="json"),
    )


# Request size limit middleware
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size for non-upload routes."""
    # Skip for upload routes
    if request.url.path.startswith("/api/v1/uploads"):
        return await call_next(request)

    # Check content-length header
    content_length = request.headers.get("content-length")
    if content_length:
        if int(content_length) > settings.max_request_body_bytes:
            request_id = getattr(request.state, "request_id", "unknown")
            envelope = ErrorEnvelope(
                error_code="PAYLOAD_TOO_LARGE",
                message=f"Request body exceeds maximum size of {settings.max_request_body_bytes} bytes",
                request_id=UUID(request_id) if request_id != "unknown" else UUID(int=0),
                timestamp=datetime.now(timezone.utc),
            )
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content=envelope.model_dump(mode="json"),
            )

    return await call_next(request)


# Include routers
app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(projects_router)
app.include_router(uploads_router)
app.include_router(websocket_router)
app.include_router(demo_router)
app.include_router(integrations_router)


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect to docs."""
    return {"message": "QA Platform API Gateway", "version": __version__, "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_gateway.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
