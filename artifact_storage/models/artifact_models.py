"""Artifact Storage database models."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Enum, Index, String, Text, event
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from artifact_storage.database import Base
from artifact_storage.schemas.enums import (
    ArtifactType,
    ScanStatus,
    ArtifactStatus,
    ExportFormat,
)


class ArtifactRecord(Base):
    """
    Central artifact record in storage.

    Represents files uploaded or written to storage with metadata and scan status.
    """

    __tablename__ = "artifact_records"

    # Primary key
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Ownership
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Project namespace for access isolation",
    )

    # Artifact metadata
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, name="artifact_type_enum"),
        nullable=False,
        index=True,
    )

    # Status tracking
    status: Mapped[ArtifactStatus] = mapped_column(
        Enum(ArtifactStatus, name="artifact_status_enum"),
        default=ArtifactStatus.UPLOADING,
        nullable=False,
        index=True,
    )

    scan_status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status_enum"),
        default=ScanStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Storage location
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        comment="Path to stored file (local or S3 key)",
    )

    # File properties
    file_size_bytes: Mapped[int] = mapped_column(
        nullable=False,
        comment="Size in bytes",
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        default="application/octet-stream",
        nullable=False,
    )

    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA256 checksum for integrity",
    )

    # Metadata
    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(32)),
        default=list,
        comment="Classification labels",
    )

    artifact_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Custom application metadata",
    )

    # Source tracking
    source_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Job that produced this artifact",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Retention
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Retention expiry; null = indefinite",
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ArtifactRecord {self.artifact_id} type={self.artifact_type.value}>"


class UploadError(Base):
    """Record of upload errors for debugging."""

    __tablename__ = "upload_errors"

    # Primary key
    error_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference to artifact if applicable
    artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Ownership
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Error details
    error_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Error classification",
    )

    error_message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    stack_trace: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<UploadError {self.error_id} type={self.error_type}>"


class ExportRequest(Base):
    """Export request tracking."""

    __tablename__ = "export_requests"

    # Primary key
    export_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Ownership
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Export metadata
    export_format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat, name="export_format_enum"),
        nullable=False,
    )

    # Filtering
    artifact_types: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
        comment="Artifact types to include; null = all",
    )

    tags_filter: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(32)),
        nullable=True,
        comment="Tag filters for artifacts",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
        index=True,
        comment="PENDING, PROCESSING, COMPLETED, FAILED",
    )

    # Results
    export_file_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Path to exported file",
    )

    export_size_bytes: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ExportRequest {self.export_id} format={self.export_format.value}>"


# Composite indexes
__table_args__ = (
    Index(
        "ix_artifact_records_project_type_created",
        ArtifactRecord.project_id,
        ArtifactRecord.artifact_type,
        ArtifactRecord.created_at.desc(),
    ),
    Index(
        "ix_artifact_records_project_tags",
        ArtifactRecord.project_id,
        ArtifactRecord.tags,
    ),
    Index(
        "ix_upload_errors_project_type_created",
        UploadError.project_id,
        UploadError.error_type,
        UploadError.created_at.desc(),
    ),
)
