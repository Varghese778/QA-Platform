"""Routes package - exports routers."""

from artifact_storage.routes.artifacts import router as artifacts_router

__all__ = ["artifacts_router"]
