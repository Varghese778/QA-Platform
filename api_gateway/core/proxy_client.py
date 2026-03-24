"""Proxy Client - Forwards requests to downstream services."""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import Request, Response

from api_gateway.config import get_settings
from api_gateway.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)
settings = get_settings()


class ProxyError(Exception):
    """Base exception for proxy errors."""

    def __init__(self, status_code: int, message: str, service: str):
        self.status_code = status_code
        self.message = message
        self.service = service
        super().__init__(message)


class UpstreamTimeout(ProxyError):
    """Raised when upstream request times out."""

    def __init__(self, service: str):
        super().__init__(
            status_code=504,
            message=f"Upstream service {service} timed out",
            service=service,
        )


class UpstreamError(ProxyError):
    """Raised when upstream returns a 5xx error."""

    def __init__(self, status_code: int, service: str, detail: Optional[str] = None):
        message = f"Upstream service {service} returned {status_code}"
        if detail:
            message += f": {detail}"
        super().__init__(
            status_code=502,
            message=message,
            service=service,
        )


class ServiceUnavailable(ProxyError):
    """Raised when service is unavailable (circuit breaker open)."""

    def __init__(self, service: str):
        super().__init__(
            status_code=503,
            message=f"Service {service} is temporarily unavailable",
            service=service,
        )


# Downstream service registry
SERVICE_REGISTRY = {
    "auth": settings.auth_service_url,
    "orchestrator": settings.orchestrator_service_url,
    "artifact": settings.artifact_service_url,
    "async": settings.async_service_url,
}


class ProxyClient:
    """
    HTTP client for forwarding requests to downstream services.

    Injects caller identity headers and enforces timeouts.
    """

    def __init__(self, timeout: Optional[float] = None):
        self.timeout = timeout or settings.downstream_timeout_seconds
        self._client: Optional[httpx.AsyncClient] = None
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get or create circuit breaker for a service."""
        if service not in self._circuit_breakers:
            self._circuit_breakers[service] = CircuitBreaker(
                name=service,
                failure_threshold=settings.circuit_breaker_failure_threshold,
                window_seconds=settings.circuit_breaker_window_seconds,
                recovery_timeout=settings.circuit_breaker_recovery_timeout_seconds,
            )
        return self._circuit_breakers[service]

    def _build_headers(
        self,
        request_id: str,
        caller_id: Optional[str] = None,
        project_id: Optional[str] = None,
        original_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Build headers for downstream request."""
        headers = {
            "X-Request-ID": request_id,
        }

        if caller_id:
            headers["X-Caller-ID"] = caller_id

        if project_id:
            headers["X-Project-ID"] = project_id

        # Forward select headers from original request
        if original_headers:
            forward_headers = ["Content-Type", "Accept", "Accept-Language"]
            for header in forward_headers:
                if header.lower() in {h.lower() for h in original_headers}:
                    # Find the actual header (case-insensitive)
                    for orig_key, orig_value in original_headers.items():
                        if orig_key.lower() == header.lower():
                            headers[header] = orig_value
                            break

        return headers

    async def forward(
        self,
        service: str,
        method: str,
        path: str,
        request_id: str,
        caller_id: Optional[str] = None,
        project_id: Optional[str] = None,
        body: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Forward a request to a downstream service.

        Args:
            service: Name of the downstream service.
            method: HTTP method.
            path: URL path (without base URL).
            request_id: Request correlation ID.
            caller_id: Authenticated user ID.
            project_id: Project context ID.
            body: Request body bytes.
            headers: Original request headers.
            query_params: Query parameters.

        Returns:
            httpx.Response from downstream service.

        Raises:
            UpstreamTimeout: On request timeout.
            UpstreamError: On 5xx response.
            ServiceUnavailable: On circuit breaker open.
        """
        base_url = SERVICE_REGISTRY.get(service)
        if not base_url:
            raise ValueError(f"Unknown service: {service}")

        circuit_breaker = self._get_circuit_breaker(service)

        # Check circuit breaker
        try:
            circuit_breaker.check()
        except CircuitBreakerOpen:
            raise ServiceUnavailable(service)

        url = f"{base_url}{path}"
        request_headers = self._build_headers(
            request_id=request_id,
            caller_id=caller_id,
            project_id=project_id,
            original_headers=headers,
        )

        client = await self.get_client()

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=request_headers,
                content=body,
                params=query_params,
            )

            # Record success for circuit breaker
            circuit_breaker.record_success()

            # Check for upstream errors (5xx)
            if response.status_code >= 500:
                circuit_breaker.record_failure()
                raise UpstreamError(
                    status_code=response.status_code,
                    service=service,
                    detail=response.text[:200] if response.text else None,
                )

            return response

        except httpx.TimeoutException:
            circuit_breaker.record_failure()
            raise UpstreamTimeout(service)

        except httpx.ConnectError as e:
            circuit_breaker.record_failure()
            logger.error(f"Connection error to {service}: {e}")
            raise ServiceUnavailable(service)

    async def forward_request(
        self,
        service: str,
        path: str,
        request: Request,
        request_id: str,
        caller_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Response:
        """
        Forward a FastAPI request to a downstream service.

        Convenience method that extracts data from FastAPI Request.
        """
        # Read request body
        body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

        # Get headers as dict
        headers = dict(request.headers)

        # Get query params
        query_params = dict(request.query_params)

        response = await self.forward(
            service=service,
            method=request.method,
            path=path,
            request_id=request_id,
            caller_id=caller_id,
            project_id=project_id,
            body=body,
            headers=headers,
            query_params=query_params if query_params else None,
        )

        # Convert to FastAPI Response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )


# Global proxy client instance
_proxy_client: Optional[ProxyClient] = None


def get_proxy_client() -> ProxyClient:
    """Get or create proxy client."""
    global _proxy_client
    if _proxy_client is None:
        _proxy_client = ProxyClient()
    return _proxy_client


async def close_proxy_client() -> None:
    """Close proxy client."""
    global _proxy_client
    if _proxy_client:
        await _proxy_client.close()
        _proxy_client = None
