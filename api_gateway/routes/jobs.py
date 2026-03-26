"""Job routes - proxied to Orchestrator and Artifact services."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from api_gateway.config import get_settings
from api_gateway.dependencies import (
    get_authenticated_user,
    get_rate_limiter,
    get_proxy,
    AuthenticatedUser,
    check_project_permission,
)
from api_gateway.core.proxy_client import ProxyClient, ProxyError, UpstreamTimeout, ServiceUnavailable
from api_gateway.core.rate_limiter import RateLimiter, RateLimitExceeded
from api_gateway.schemas import (
    ErrorEnvelope,
    JobSubmitRequest,
    JobSubmitResponse,
    JobListResponse,
    JobDetailResponse,
    JobCancelResponse,
    JobTestsResponse,
    JobReportResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _create_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
) -> Response:
    """Create a standard error response."""
    from datetime import datetime, timezone
    import json

    request.state.error_code = error_code

    envelope = ErrorEnvelope(
        error_code=error_code,
        message=message,
        request_id=UUID(request.state.request_id),
        timestamp=datetime.now(timezone.utc),
    )

    return Response(
        content=json.dumps(envelope.model_dump(), default=str),
        status_code=status_code,
        media_type="application/json",
    )


@router.post("", response_model=JobSubmitResponse, status_code=201)
async def submit_job(
    job_request: JobSubmitRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Submit a new QA job.

    Requires QA_ENGINEER, PROJECT_ADMIN, or ORG_ADMIN role in the target project.
    """
    project_id = str(job_request.project_id)

    # Check project permission
    await check_project_permission(
        user=user,
        project_id=project_id,
        required_roles={"QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
        request=request,
    )

    # Apply rate limiting
    try:
        user_result, project_result = await rate_limiter.check_limits(
            user_id=user.user_id,
            project_id=project_id,
        )
    except RateLimitExceeded as e:
        request.state.rate_limit_hit = True
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {e.limit_type}",
            headers={
                "X-RateLimit-Limit": str(e.limit),
                "X-RateLimit-Remaining": str(e.remaining),
                "X-RateLimit-Reset": str(e.reset_at),
            },
        )

    # Set tracking info
    request.state.upstream_service = "orchestrator"
    request.state.project_id = project_id

    # Forward to Orchestrator
    try:
        return await proxy.forward_request(
            service="orchestrator",
            path="/internal/v1/jobs",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
            project_id=project_id,
        )
    except UpstreamTimeout:
        return _create_error_response(
            request, 504, "UPSTREAM_TIMEOUT", "Orchestrator service timed out"
        )
    except ServiceUnavailable:
        return _create_error_response(
            request, 503, "SERVICE_UNAVAILABLE", "Orchestrator service unavailable"
        )
    except ProxyError as e:
        return _create_error_response(
            request, 502, "UPSTREAM_ERROR", e.message
        )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    project_id: UUID = Query(..., description="Project to list jobs from"),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    List jobs in a project.

    Requires membership in the target project.
    """
    project_id_str = str(project_id)

    # Check project permission (VIEWER and above)
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
            detail=f"Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(e.limit),
                "X-RateLimit-Remaining": str(e.remaining),
                "X-RateLimit-Reset": str(e.reset_at),
            },
        )

    request.state.upstream_service = "orchestrator"
    request.state.project_id = project_id_str

    try:
        return await proxy.forward_request(
            service="orchestrator",
            path="/internal/v1/jobs",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
            project_id=project_id_str,
        )
    except (UpstreamTimeout, ServiceUnavailable, ProxyError) as e:
        return _create_error_response(
            request, 502 if isinstance(e, ProxyError) else 503,
            "UPSTREAM_ERROR", str(e)
        )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Get job details.

    Requires membership in the job's project.
    """
    request.state.upstream_service = "orchestrator"

    try:
        return await proxy.forward_request(
            service="orchestrator",
            path=f"/internal/v1/jobs/{job_id}",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
        )
    except (UpstreamTimeout, ServiceUnavailable, ProxyError) as e:
        return _create_error_response(
            request, 502, "UPSTREAM_ERROR", str(e)
        )


@router.delete("/{job_id}", response_model=JobCancelResponse)
async def cancel_job(
    job_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Cancel a queued job.

    Requires QA_ENGINEER role (own jobs) or PROJECT_ADMIN/ORG_ADMIN (any job).
    Note: Orchestrator expects POST to /cancel, so we override the method and path.
    """
    request.state.upstream_service = "orchestrator"

    try:
        response = await proxy.forward(
            service="orchestrator",
            method="POST",
            path=f"/internal/v1/jobs/{job_id}/cancel",
            request_id=request.state.request_id,
            caller_id=user.user_id,
        )
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json",
        )
    except (UpstreamTimeout, ServiceUnavailable, ProxyError) as e:
        return _create_error_response(
            request, 502, "UPSTREAM_ERROR", str(e)
        )


@router.get("/{job_id}/tests", response_model=JobTestsResponse)
async def get_job_tests(
    job_id: UUID,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status_filter"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Get test cases for a job.

    Requires membership in the job's project.
    """
    request.state.upstream_service = "artifact"

    try:
        return await proxy.forward_request(
            service="artifact",
            path=f"/internal/v1/artifacts/{job_id}/tests",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
        )
    except (UpstreamTimeout, ServiceUnavailable, ProxyError) as e:
        return _create_error_response(
            request, 502, "UPSTREAM_ERROR", str(e)
        )


@router.get("/{job_id}/report", response_model=JobReportResponse)
async def get_job_report(
    job_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Get execution report for a job.

    Requires membership in the job's project.
    """
    request.state.upstream_service = "artifact"

    try:
        return await proxy.forward_request(
            service="artifact",
            path=f"/internal/v1/artifacts/{job_id}/report",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
        )
    except (UpstreamTimeout, ServiceUnavailable, ProxyError) as e:
        return _create_error_response(
            request, 502, "UPSTREAM_ERROR", str(e)
        )


@router.get("/{job_id}/export")
async def export_job_report(
    job_id: UUID,
    request: Request,
    format: str = Query("pdf", regex="^(pdf|csv)$"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Export job report in PDF or CSV format.

    Requires QA_ENGINEER role or above in the job's project.
    """
    request.state.upstream_service = "artifact"

    try:
        response = await proxy.forward_request(
            service="artifact",
            path=f"/internal/v1/artifacts/{job_id}/export",
            request=request,
            request_id=request.state.request_id,
            caller_id=user.user_id,
        )

        # Override content type and add disposition header for downloads
        content_type = "application/pdf" if format == "pdf" else "text/csv"
        response.media_type = content_type
        response.headers["Content-Disposition"] = f'attachment; filename="report-{job_id}.{format}"'

        return response
    except (UpstreamTimeout, ServiceUnavailable, ProxyError) as e:
        return _create_error_response(
            request, 502, "UPSTREAM_ERROR", str(e)
        )
