"""Pydantic schemas for Artifact Storage."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from artifact_storage.schemas.enums import (
    ArtifactType,
    ScanStatus,
    ArtifactStatus,
    ExportFormat,
)


# =====================================================================
# Upload/Write Schemas
# =====================================================================


class UploadRequest(BaseModel):
    """Request for uploading an artifact."""

    project_id: UUID
    artifact_type: ArtifactType
    source_job_id: Optional[UUID] = None
    tags: Optional[List[str]] = Field(default=None, max_length=20)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class WriteRequest(BaseModel):
    """Service-to-service binary write request."""

    project_id: UUID
    artifact_id: Optional[UUID] = None
    artifact_type: ArtifactType
    source_job_id: Optional[UUID] = None
    tags: Optional[List[str]] = Field(default=None, max_length=20)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    binary_data: bytes = Field(..., description="Raw binary content")


# =====================================================================
# Artifact Response Schemas
# =====================================================================


class ArtifactRecord(BaseModel):
    """Full artifact record response."""

    artifact_id: UUID
    project_id: UUID
    artifact_type: ArtifactType
    status: ArtifactStatus
    scan_status: ScanStatus
    file_path: str
    file_size_bytes: int
    mime_type: str
    checksum_sha256: str
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    source_job_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    version: int


class UploadedArtifactResponse(BaseModel):
    """Response after uploading an artifact."""

    artifact_id: UUID
    project_id: UUID
    artifact_type: ArtifactType
    status: ArtifactStatus
    created_at: datetime


class PreSignedURLResponse(BaseModel):
    """Response with pre-signed URL for artifact access."""

    artifact_id: UUID
    download_url: str
    expires_at: datetime
    http_method: str = "GET"


class ListArtifactsResponse(BaseModel):
    """Response for listing artifacts."""

    artifacts: List[ArtifactRecord]
    total_count: int
    limit: int
    offset: int


class UploadErrorRecord(BaseModel):
    """Record of an upload error."""

    error_id: UUID
    artifact_id: Optional[UUID] = None
    project_id: UUID
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    created_at: datetime


class ExportRequestSchema(BaseModel):
    """Export request."""

    export_id: UUID
    project_id: UUID
    export_format: ExportFormat
    artifact_types: Optional[List[ArtifactType]] = None
    tags_filter: Optional[List[str]] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    export_file_path: Optional[str] = None
    export_size_bytes: Optional[int] = None


class CreateExportRequest(BaseModel):
    """Request to create an export."""

    project_id: UUID
    export_format: ExportFormat
    artifact_types: Optional[List[ArtifactType]] = None
    tags_filter: Optional[List[str]] = None


# =====================================================================
# Health & Status
# =====================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    storage_available: bool = True
    database_latency_ms: int = 0
    redis_latency_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    """Error detail response."""

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
