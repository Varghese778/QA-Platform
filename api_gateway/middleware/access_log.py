"""Access log middleware - writes structured access log for every request."""

import json
import logging
import time
from typing import Callable, Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api_gateway.schemas.access_log import AccessLogRecord

# Configure access logger
access_logger = logging.getLogger("api_gateway.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log structured access records for every request.

    Captures:
    - Request metadata (method, path, headers)
    - Response status code
    - Processing latency
    - Caller identity (if authenticated)
    - Rate limit status
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and write access log."""
        start_time = time.time()

        # Get request ID (set by RequestIDMiddleware)
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            request_id = UUID(request_id)
        else:
            import uuid
            request_id = uuid.uuid4()

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Get user agent
        user_agent = request.headers.get("User-Agent")

        # Initialize state for tracking
        request.state.upstream_service = None
        request.state.rate_limit_hit = False
        request.state.error_code = None

        # Process request
        response = await call_next(request)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Get caller/project IDs if set during auth
        caller_id = getattr(request.state, "caller_id", None)
        project_id = getattr(request.state, "project_id", None)

        # Get tracking info
        upstream_service = getattr(request.state, "upstream_service", None)
        rate_limit_hit = getattr(request.state, "rate_limit_hit", False)
        error_code = getattr(request.state, "error_code", None)

        # Build access log record
        log_record = AccessLogRecord(
            request_id=request_id,
            caller_id=UUID(caller_id) if caller_id else None,
            project_id=UUID(project_id) if project_id else None,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            upstream_service=upstream_service,
            rate_limit_hit=rate_limit_hit,
            client_ip=client_ip,
            user_agent=user_agent,
            error_code=error_code,
        )

        # Write structured log
        access_logger.info(json.dumps(log_record.to_dict()))

        return response

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP from request."""
        # Check X-Forwarded-For header (set by load balancer/proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client
        if request.client:
            return request.client.host

        return None
