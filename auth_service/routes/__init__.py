"""Routes package - exports all route modules."""

from auth_service.routes.auth import router as auth_router
from auth_service.routes.users import router as users_router
from auth_service.routes.projects import router as projects_router
from auth_service.routes.projects import invitations_router
from auth_service.routes.internal import router as internal_router

__all__ = [
    "auth_router",
    "users_router",
    "projects_router",
    "invitations_router",
    "internal_router",
]
