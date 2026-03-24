"""Routes package - exports all API routers."""

from multi_agent_engine.routes.tasks import router as tasks_router

__all__ = [
    "tasks_router",
]
