"""Common schemas - Error envelope and health responses."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Field-level error detail."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error description for this field")
    code: Optional[str] = Field(None, description="Machine-readable error code")


class ErrorEnvelope(BaseModel):
    """
    Canonical error response format.

    All errors from the gateway use this format.
    """

    error_code: str = Field(
        ...,
        description="Machine-readable error identifier",
        examples=["VALIDATION_ERROR", "UNAUTHORIZED", "RATE_LIMIT_EXCEEDED"],
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
    )
    details: Optional[List[ErrorDetail]] = Field(
        None,
        description="Field-level errors where applicable",
    )
    request_id: UUID = Field(
        ...,
        description="Request correlation ID for tracing",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Error generation time",
    )


class DependencyStatus(BaseModel):
    """Status of a dependency service."""

    name: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status", examples=["healthy", "unhealthy"])
    latency_ms: Optional[int] = Field(None, description="Response latency in ms")


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str = Field(default="ok", description="Service status")


class ReadyResponse(BaseModel):
    """Readiness probe response."""

    status: str = Field(default="ok", description="Service status")
    dependencies: List[DependencyStatus] = Field(
        default_factory=list,
        description="Status of downstream dependencies",
    )
