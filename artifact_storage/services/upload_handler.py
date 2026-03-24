"""Upload handler and artifact persistence."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import mimetypes
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from artifact_storage.config import get_settings
from artifact_storage.models import ArtifactRecord, UploadError
from artifact_storage.schemas.enums import ArtifactType, ArtifactStatus, ScanStatus
from artifact_storage.services.storage_provider import get_storage_provider

logger = logging.getLogger(__name__)
settings = get_settings()


class UploadHandler:
    """Handles file uploads and validation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage_provider()

    async def validate_upload(
        self,
        project_id: UUID,
        filename: str,
        file_data: bytes,
        artifact_type: ArtifactType,
    ) -> dict:
        """
        Validate uploaded file.

        Args:
            project_id: Project ID
            filename: Original filename
            file_data: File binary content
            artifact_type: Type of artifact

        Returns:
            Validation result with checksum and metadata

        Raises:
            ValueError: If validation fails
        """
        # Check size
        if len(file_data) > settings.max_upload_size_bytes:
            raise ValueError(
                f"File exceeds maximum size of {settings.max_upload_size_bytes} bytes"
            )

        if len(file_data) == 0:
            raise ValueError("File is empty")

        # Calculate checksum
        checksum = hashlib.sha256(file_data).hexdigest()

        # Check for duplicates
        stmt = select(ArtifactRecord).where(
            ArtifactRecord.checksum_sha256 == checksum,
            ArtifactRecord.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(
                f"File with same content already exists (artifact_id={existing.artifact_id})"
            )

        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = "application/octet-stream"

        return {
            "checksum": checksum,
            "mime_type": mime_type,
            "size": len(file_data),
        }

    async def record_upload_error(
        self,
        project_id: UUID,
        error_type: str,
        error_message: str,
        artifact_id: Optional[UUID] = None,
        stack_trace: Optional[str] = None,
    ) -> UUID:
        """Record an upload error for debugging."""
        error = UploadError(
            artifact_id=artifact_id,
            project_id=project_id,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
        )
        self.db.add(error)
        await self.db.flush()

        logger.warning(
            f"Recorded upload error {error.error_id}: {error_type} - {error_message}"
        )
        return error.error_id


class ArtifactPersister:
    """Persists artifacts to storage."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage_provider()

    async def create_artifact(
        self,
        project_id: UUID,
        artifact_type: ArtifactType,
        artifact_id: UUID,
        binary_data: bytes,
        mime_type: str,
        checksum: str,
        source_job_id: Optional[UUID] = None,
        tags: Optional[list] = None,
        metadata: Optional[dict] = None,
        expires_at: Optional[datetime] = None,
    ) -> ArtifactRecord:
        """
        Create and persist an artifact.

        Args:
            project_id: Project ID
            artifact_type: Type of artifact
            artifact_id: Artifact ID
            binary_data: File binary content
            mime_type: MIME type
            checksum: SHA256 checksum
            source_job_id: Source job that created artifact
            tags: Classification tags
            metadata: Custom metadata
            expires_at: Expiration timestamp

        Returns:
            Created ArtifactRecord
        """
        try:
            # Write to storage
            file_path = await self.storage.write(
                str(project_id), str(artifact_id), binary_data
            )

            # Create database record
            artifact = ArtifactRecord(
                artifact_id=artifact_id,
                project_id=project_id,
                artifact_type=artifact_type,
                status=ArtifactStatus.UPLOADING,
                scan_status=ScanStatus.PENDING if settings.enable_virus_scan else ScanStatus.CLEAN,
                file_path=file_path,
                file_size_bytes=len(binary_data),
                mime_type=mime_type,
                checksum_sha256=checksum,
                source_job_id=source_job_id,
                tags=tags or [],
                metadata=metadata or {},
                expires_at=expires_at,
            )

            self.db.add(artifact)
            await self.db.flush()

            logger.info(
                f"Created artifact {artifact_id} in project {project_id} "
                f"({len(binary_data)} bytes)"
            )

            return artifact

        except Exception as e:
            logger.error(f"Failed to create artifact: {e}")
            raise

    async def update_artifact(
        self,
        artifact_id: UUID,
        project_id: UUID,
        **updates,
    ) -> ArtifactRecord:
        """
        Update an artifact record.

        Args:
            artifact_id: Artifact ID
            project_id: Project ID
            **updates: Fields to update

        Returns:
            Updated ArtifactRecord

        Raises:
            ValueError: If artifact not found
        """
        stmt = select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id,
            ArtifactRecord.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        # Update fields
        for key, value in updates.items():
            if hasattr(artifact, key):
                setattr(artifact, key, value)

        artifact.updated_at = datetime.now(timezone.utc)
        artifact.version += 1

        await self.db.flush()

        logger.info(f"Updated artifact {artifact_id}")
        return artifact

    async def get_artifact(
        self, artifact_id: UUID, project_id: UUID
    ) -> Optional[ArtifactRecord]:
        """Get an artifact record."""
        stmt = select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id,
            ArtifactRecord.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_artifact(
        self, artifact_id: UUID, project_id: UUID, hard_delete: bool = False
    ) -> bool:
        """
        Delete an artifact.

        Args:
            artifact_id: Artifact ID
            project_id: Project ID
            hard_delete: If True, delete from storage; if False, mark as DELETED

        Returns:
            True if deleted, False if not found
        """
        artifact = await self.get_artifact(artifact_id, project_id)

        if not artifact:
            return False

        if hard_delete:
            # Delete from storage
            await self.storage.delete(str(project_id), str(artifact_id))
            # Delete from database
            await self.db.delete(artifact)
            logger.info(f"Hard deleted artifact {artifact_id}")
        else:
            # Soft delete
            artifact.status = ArtifactStatus.DELETED
            artifact.updated_at = datetime.now(timezone.utc)
            logger.info(f"Soft deleted artifact {artifact_id}")

        await self.db.flush()
        return True
