"""Project routes - proxied to Auth service."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api_gateway.config import get_settings
from api_gateway.dependencies import (
    get_authenticated_user,
    get_rate_limiter,
    get_proxy,
    AuthenticatedUser,
    check_project_permission,
)
from api_gateway.core.proxy_client import ProxyClient, ProxyError
from api_gateway.core.rate_limiter import RateLimiter, RateLimitExceeded
from api_gateway.schemas import ProjectListResponse, ProjectResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    List projects the authenticated user is a member of.
    """
    # Apply rate limiting
    try:
        await rate_limiter.check_limits(user_id=user.user_id)
    except RateLimitExceeded as e:
        request.state.rate_limit_hit = True
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(e.limit),
                "X-RateLimit-Remaining": str(e.remaining),
                "X-RateLimit-Reset": str(e.reset_at),
            },
        )

    request.state.upstream_service = "auth"

    try:
        response = await proxy.forward_request(
            service="auth",
            path="/auth/v1/projects",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
        )
        return Response(
            content=response.body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json",
        )
    except ProxyError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream error: {e.message}",
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Get project details.

    Requires membership in the project.
    """
    project_id_str = str(project_id)

    # Check project permission
    await check_project_permission(
        user=user,
        project_id=project_id_str,
        required_roles={"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
        request=request,
    )

    # Apply rate limiting
    try:
        await rate_limiter.check_limits(user_id=user.user_id, project_id=project_id_str)
    except RateLimitExceeded as e:
        request.state.rate_limit_hit = True
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(e.limit),
                "X-RateLimit-Remaining": str(e.remaining),
                "X-RateLimit-Reset": str(e.reset_at),
            },
        )

    request.state.upstream_service = "auth"
    request.state.project_id = project_id_str

    try:
        response = await proxy.forward_request(
            service="auth",
            path=f"/auth/v1/projects/{project_id}",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
            project_id=project_id_str,
        )
        return Response(
            content=response.body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json",
        )
    except ProxyError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream error: {e.message}",
        )
