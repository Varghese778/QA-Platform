"""Routes package - exports all route modules."""

from api_gateway.routes.health import router as health_router
from api_gateway.routes.jobs import router as jobs_router
from api_gateway.routes.projects import router as projects_router
from api_gateway.routes.uploads import router as uploads_router
from api_gateway.routes.websocket import router as websocket_router

__all__ = [
    "health_router",
    "jobs_router",
    "projects_router",
    "uploads_router",
    "websocket_router",
]
