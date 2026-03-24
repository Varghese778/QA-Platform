"""Upload routes - proxied to Artifact Storage service."""

import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from api_gateway.config import get_settings
from api_gateway.dependencies import (
    get_authenticated_user,
    get_rate_limiter,
    get_proxy,
    AuthenticatedUser,
)
from api_gateway.core.proxy_client import ProxyClient, ProxyError
from api_gateway.core.rate_limiter import RateLimiter, RateLimitExceeded
from api_gateway.schemas import UploadResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(..., description="Files to upload"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    proxy: ProxyClient = Depends(get_proxy),
):
    """
    Upload files for a QA job.

    Limits:
    - Maximum 10 MB per file
    - Maximum 5 files per request

    Requires QA_ENGINEER role or above.
    """
    # Validate file count
    if len(files) > settings.max_upload_files_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.max_upload_files_count} files allowed per request",
        )

    # Validate file sizes
    for file in files:
        # Read a small chunk to check if file is too large
        # Note: For production, use streaming/chunked upload
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        if len(content) > settings.max_upload_file_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {file.filename} exceeds maximum size of {settings.max_upload_file_bytes // 1024 // 1024} MB",
            )

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

    request.state.upstream_service = "artifact"

    # Build multipart form data for forwarding
    try:
        # For multipart uploads, we need to forward differently
        import httpx

        form_files = []
        for file in files:
            content = await file.read()
            form_files.append(
                ("files", (file.filename, content, file.content_type or "application/octet-stream"))
            )

        async with httpx.AsyncClient(timeout=settings.downstream_timeout_seconds) as client:
            response = await client.post(
                f"{settings.artifact_service_url}/internal/v1/uploads",
                files=form_files,
                headers={
                    "X-Request-ID": request.state.request_id,
                    "X-Caller-ID": user.user_id,
                },
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upload service timed out",
        )
    except Exception as e:
        logger.error(f"Upload proxy error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to proxy upload request",
        )
