"""Access log record schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AccessLogRecord(BaseModel):
    """
    Structured access log record.

    Written for every request processed by the gateway.
    """

    request_id: UUID = Field(..., description="Correlation ID")
    caller_id: Optional[UUID] = Field(None, description="Authenticated user ID")
    project_id: Optional[UUID] = Field(None, description="Project context if present")
    method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Normalized request path")
    status_code: int = Field(..., description="HTTP response status")
    latency_ms: int = Field(..., description="Total processing time in ms")
    upstream_service: Optional[str] = Field(None, description="Downstream service name")
    rate_limit_hit: bool = Field(default=False, description="Whether rate limit was applied")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Request receipt timestamp",
    )
    client_ip: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    error_code: Optional[str] = Field(None, description="Error code if request failed")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON logging."""
        return {
            "request_id": str(self.request_id),
            "caller_id": str(self.caller_id) if self.caller_id else None,
            "project_id": str(self.project_id) if self.project_id else None,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "upstream_service": self.upstream_service,
            "rate_limit_hit": self.rate_limit_hit,
            "timestamp": self.timestamp.isoformat(),
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "error_code": self.error_code,
        }
