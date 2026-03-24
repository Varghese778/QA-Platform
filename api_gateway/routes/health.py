"""Health check endpoints."""

import logging
import time
from typing import Optional

import httpx
import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, status

from api_gateway.config import get_settings
from api_gateway.core.rate_limiter import get_redis
from api_gateway.schemas import HealthResponse, ReadyResponse, DependencyStatus

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def liveness_probe() -> HealthResponse:
    """
    Liveness probe endpoint.

    Returns 200 if the gateway process is running.
    Used by Kubernetes/load balancer for health checks.
    """
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness_probe() -> ReadyResponse:
    """
    Readiness probe endpoint.

    Checks connectivity to critical dependencies:
    - Redis (rate limiting)
    - Auth service (JWKS)

    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    dependencies = []
    all_healthy = True

    # Check Redis
    redis_status = await _check_redis()
    dependencies.append(redis_status)
    if redis_status.status != "healthy":
        all_healthy = False

    # Check Auth service (JWKS)
    auth_status = await _check_auth_service()
    dependencies.append(auth_status)
    if auth_status.status != "healthy":
        all_healthy = False

    # Check Orchestrator service
    orchestrator_status = await _check_service(
        name="orchestrator",
        url=f"{settings.orchestrator_service_url}/health",
    )
    dependencies.append(orchestrator_status)

    # Check Artifact service
    artifact_status = await _check_service(
        name="artifact",
        url=f"{settings.artifact_service_url}/health",
    )
    dependencies.append(artifact_status)

    if not all_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "dependencies": [d.model_dump() for d in dependencies],
            },
        )

    return ReadyResponse(status="ok", dependencies=dependencies)


async def _check_redis() -> DependencyStatus:
    """Check Redis connectivity."""
    start = time.time()
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        latency = int((time.time() - start) * 1000)
        return DependencyStatus(name="redis", status="healthy", latency_ms=latency)
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return DependencyStatus(name="redis", status="unhealthy", latency_ms=None)


async def _check_auth_service() -> DependencyStatus:
    """Check Auth service JWKS endpoint."""
    start = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(settings.jwks_url, timeout=5.0)
            response.raise_for_status()
            latency = int((time.time() - start) * 1000)
            return DependencyStatus(name="auth", status="healthy", latency_ms=latency)
    except Exception as e:
        logger.warning(f"Auth service health check failed: {e}")
        return DependencyStatus(name="auth", status="unhealthy", latency_ms=None)


async def _check_service(name: str, url: str) -> DependencyStatus:
    """Check a downstream service health endpoint."""
    start = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            latency = int((time.time() - start) * 1000)
            if response.status_code < 500:
                return DependencyStatus(name=name, status="healthy", latency_ms=latency)
            return DependencyStatus(name=name, status="unhealthy", latency_ms=latency)
    except Exception as e:
        logger.warning(f"{name} health check failed: {e}")
        return DependencyStatus(name=name, status="unhealthy", latency_ms=None)
