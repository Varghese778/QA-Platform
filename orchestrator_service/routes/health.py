"""Health check routes."""

from datetime import datetime, timezone

from fastapi import APIRouter

from orchestrator_service import __version__
from orchestrator_service.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    """
    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health/live", response_model=HealthResponse)
async def liveness_check():
    """
    Liveness probe for Kubernetes.

    Returns 200 if the service is running.
    """
    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness probe for Kubernetes.

    Returns 200 if the service can accept traffic.
    In production, this would check database and downstream service connectivity.
    """
    # MVP: Simple check
    # In production, would verify:
    # - Database connection
    # - Redis connection
    # - Downstream service availability

    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )
