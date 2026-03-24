"""API routes for Artifact Storage."""

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from artifact_storage.config import get_settings
from artifact_storage.database import get_db
from artifact_storage.models import ArtifactRecord, ExportRequest, UploadError
from artifact_storage.schemas.enums import (
    ArtifactType,
    ArtifactStatus,
    ExportFormat,
)
from artifact_storage.schemas.tasks import (
    UploadedArtifactResponse,
    ArtifactRecord as ArtifactRecordSchema,
    PreSignedURLResponse,
    ListArtifactsResponse,
    UploadErrorRecord,
    ExportRequestSchema,
    CreateExportRequest,
    HealthResponse,
)
from artifact_storage.services.access_enforcer import AccessEnforcer, check_cross_project_access
from artifact_storage.services.upload_handler import UploadHandler, ArtifactPersister
from artifact_storage.services.presigned_url_generator import PreSignedURLGenerator
from artifact_storage.services.virus_scanner import VirusScanner

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/internal/v1", tags=["artifact-storage"])


# =====================================================================
# Upload Endpoints
# =====================================================================


@router.post("/uploads", response_model=UploadedArtifactResponse, status_code=status.HTTP_201_CREATED)
async def upload_context_file(
    project_id: UUID = Form(...),
    artifact_type: ArtifactType = Form(...),
    file: UploadFile = File(...),
    source_job_id: Optional[UUID] = Form(None),
    tags: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a context file (multipart form)."""
    try:
        # Check access
        AccessEnforcer.check_project_access(project_id)

        # Read file
        file_data = await file.read()
        filename = file.filename or "unknown"

        # Validate
        handler = UploadHandler(db)
        validation = await handler.validate_upload(
            project_id, filename, file_data, artifact_type
        )

        # Create artifact
        from uuid import uuid4
        artifact_id = uuid4()

        persister = ArtifactPersister(db)
        artifact = await persister.create_artifact(
            project_id=project_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            binary_data=file_data,
            mime_type=validation["mime_type"],
            checksum=validation["checksum"],
            source_job_id=source_job_id,
            tags=tags.split(",") if tags else [],
        )

        # Enqueue virus scan if enabled
        if settings.enable_virus_scan:
            scanner = VirusScanner(db)
            await scanner.connect()
            await scanner.enqueue_scan(project_id, artifact.artifact_id)
            await scanner.disconnect()

        await db.commit()

        return UploadedArtifactResponse(
            artifact_id=artifact.artifact_id,
            project_id=artifact.project_id,
            artifact_type=artifact.artifact_type,
            status=artifact.status,
            created_at=artifact.created_at,
        )

    except ValueError as e:
        logger.error(f"Upload validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed",
        )


@router.post("/artifacts", response_model=UploadedArtifactResponse, status_code=status.HTTP_201_CREATED)
async def write_artifact_binary(
    project_id: UUID = Form(...),
    artifact_type: ArtifactType = Form(...),
    binary_data: bytes = File(...),
    artifact_id: Optional[UUID] = Form(None),
    source_job_id: Optional[UUID] = Form(None),
    tags: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Service-to-service binary write."""
    try:
        # Check access
        AccessEnforcer.check_project_access(project_id)

        # Generate artifact ID if not provided
        from uuid import uuid4
        if not artifact_id:
            artifact_id = uuid4()

        # Validate and compute checksum
        if len(binary_data) > settings.max_upload_size_bytes:
            raise ValueError("Binary data exceeds maximum size")

        import hashlib
        checksum = hashlib.sha256(binary_data).hexdigest()

        import mimetypes
        mime_type = "application/octet-stream"

        # Create artifact
        persister = ArtifactPersister(db)
        artifact = await persister.create_artifact(
            project_id=project_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            binary_data=binary_data,
            mime_type=mime_type,
            checksum=checksum,
            source_job_id=source_job_id,
            tags=tags.split(",") if tags else [],
        )

        # Enqueue virus scan
        if settings.enable_virus_scan:
            scanner = VirusScanner(db)
            await scanner.connect()
            await scanner.enqueue_scan(project_id, artifact.artifact_id)
            await scanner.disconnect()

        await db.commit()

        return UploadedArtifactResponse(
            artifact_id=artifact.artifact_id,
            project_id=artifact.project_id,
            artifact_type=artifact.artifact_type,
            status=artifact.status,
            created_at=artifact.created_at,
        )

    except Exception as e:
        logger.error(f"Binary write failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Binary write failed",
        )


# =====================================================================
# Artifact CRUD Endpoints
# =====================================================================


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRecordSchema)
async def get_artifact(
    artifact_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get an artifact by ID."""
    try:
        # Check access
        AccessEnforcer.check_project_access(project_id)

        stmt = select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id,
            ArtifactRecord.project_id == project_id,
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if not artifact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact {artifact_id} not found",
            )

        return ArtifactRecordSchema(
            artifact_id=artifact.artifact_id,
            project_id=artifact.project_id,
            artifact_type=artifact.artifact_type,
            status=artifact.status,
            scan_status=artifact.scan_status,
            file_path=artifact.file_path,
            file_size_bytes=artifact.file_size_bytes,
            mime_type=artifact.mime_type,
            checksum_sha256=artifact.checksum_sha256,
            tags=artifact.tags,
            metadata=artifact.metadata,
            source_job_id=artifact.source_job_id,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
            expires_at=artifact.expires_at,
            version=artifact.version,
        )

    except Exception as e:
        logger.error(f"Failed to get artifact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get artifact",
        )


@router.put("/artifacts/{artifact_id}", response_model=ArtifactRecordSchema)
async def update_artifact(
    artifact_id: UUID,
    project_id: UUID = Form(...),
    tags: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Update an artifact."""
    try:
        # Check access
        AccessEnforcer.check_project_access(project_id)

        await check_cross_project_access(project_id, project_id)

        persister = ArtifactPersister(db)
        updates = {}
        if tags:
            updates["tags"] = tags.split(",")
        if metadata:
            import json
            updates["metadata"] = json.loads(metadata)

        artifact = await persister.update_artifact(artifact_id, project_id, **updates)
        await db.commit()

        return ArtifactRecordSchema(
            artifact_id=artifact.artifact_id,
            project_id=artifact.project_id,
            artifact_type=artifact.artifact_type,
            status=artifact.status,
            scan_status=artifact.scan_status,
            file_path=artifact.file_path,
            file_size_bytes=artifact.file_size_bytes,
            mime_type=artifact.mime_type,
            checksum_sha256=artifact.checksum_sha256,
            tags=artifact.tags,
            metadata=artifact.metadata,
            source_job_id=artifact.source_job_id,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
            expires_at=artifact.expires_at,
            version=artifact.version,
        )

    except Exception as e:
        logger.error(f"Update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Update failed",
        )


@router.delete("/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact(
    artifact_id: UUID,
    project_id: UUID = Query(...),
    hard_delete: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Delete an artifact."""
    try:
        # Check access
        AccessEnforcer.check_project_access(project_id)

        persister = ArtifactPersister(db)
        deleted = await persister.delete_artifact(
            artifact_id, project_id, hard_delete=hard_delete
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        await db.commit()

    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete failed",
        )


# =====================================================================
# Download/Pre-Signed URL Endpoints
# =====================================================================


@router.get("/artifacts/{artifact_id}/url", response_model=PreSignedURLResponse)
async def get_presigned_url(
    artifact_id: UUID,
    project_id: UUID = Query(...),
    ttl_seconds: int = Query(3600, ge=60, le=86400),
    db: AsyncSession = Depends(get_db),
):
    """Get a pre-signed URL for downloading an artifact."""
    try:
        # Check access
        AccessEnforcer.check_project_access(project_id)

        # Verify artifact exists
        stmt = select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id,
            ArtifactRecord.project_id == project_id,
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if not artifact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        # Generate URL
        from starlette.requests import Request
        # In a real app, we'd get the base URL from the request
        base_url = "http://localhost:8012"

        download_url, expires_at = PreSignedURLGenerator.generate_download_url(
            artifact_id, project_id, base_url, ttl_seconds
        )

        return PreSignedURLResponse(
            artifact_id=artifact_id,
            download_url=download_url,
            expires_at=expires_at,
            http_method="GET",
        )

    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL",
        )


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Download an artifact using pre-signed token."""
    try:
        # Verify token
        payload = PreSignedURLGenerator.verify_token(token)
        project_id = UUID(payload["project_id"])

        await check_cross_project_access(project_id, project_id)

        # Get artifact
        stmt = select(ArtifactRecord).where(
            ArtifactRecord.artifact_id == artifact_id,
            ArtifactRecord.project_id == project_id,
        )
        result = await db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if not artifact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        # Read from storage
        from artifact_storage.services.storage_provider import get_storage_provider
        storage = get_storage_provider()
        binary_data = await storage.read(str(project_id), str(artifact_id))

        return StreamingResponse(
            BytesIO(binary_data),
            media_type=artifact.mime_type,
            headers={"Content-Disposition": f"attachment; filename={artifact_id}"},
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Download failed",
        )


# =====================================================================
# List Endpoints
# =====================================================================


@router.get("/artifacts", response_model=ListArtifactsResponse)
async def list_artifacts(
    project_id: UUID = Query(...),
    artifact_type: Optional[ArtifactType] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List artifacts in a project."""
    try:
        # Check access
        AccessEnforcer.check_project_access(project_id)

        # Build query
        stmt = select(ArtifactRecord).where(
            ArtifactRecord.project_id == project_id
        )

        if artifact_type:
            stmt = stmt.where(ArtifactRecord.artifact_type == artifact_type)

        # Get total count
        count_stmt = select(ArtifactRecord).where(
            ArtifactRecord.project_id == project_id
        )
        if artifact_type:
            count_stmt = count_stmt.where(ArtifactRecord.artifact_type == artifact_type)

        from sqlalchemy import func
        count_result = await db.execute(select(func.count()).select_from(count_stmt))
        total_count = count_result.scalar()

        # Get paginated results
        stmt = stmt.offset(offset).limit(limit)
        result = await db.execute(stmt)
        artifacts = result.scalars().all()

        artifact_schemas = [
            ArtifactRecordSchema(
                artifact_id=a.artifact_id,
                project_id=a.project_id,
                artifact_type=a.artifact_type,
                status=a.status,
                scan_status=a.scan_status,
                file_path=a.file_path,
                file_size_bytes=a.file_size_bytes,
                mime_type=a.mime_type,
                checksum_sha256=a.checksum_sha256,
                tags=a.tags,
                metadata=a.metadata,
                source_job_id=a.source_job_id,
                created_at=a.created_at,
                updated_at=a.updated_at,
                expires_at=a.expires_at,
                version=a.version,
            )
            for a in artifacts
        ]

        return ListArtifactsResponse(
            artifacts=artifact_schemas,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"List failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="List failed",
        )


# =====================================================================
# Export Endpoints
# =====================================================================


@router.post("/artifacts/export", response_model=ExportRequestSchema, status_code=status.HTTP_202_ACCEPTED)
async def create_export(
    request: CreateExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create an export request."""
    try:
        # Check access
        AccessEnforcer.check_project_access(request.project_id)

        # Create export request
        from uuid import uuid4
        export = ExportRequest(
            export_id=uuid4(),
            project_id=request.project_id,
            export_format=request.export_format,
            artifact_types=request.artifact_types,
            tags_filter=request.tags_filter,
            status="PENDING",
        )

        db.add(export)
        await db.flush()

        logger.info(f"Created export request {export.export_id}")

        return ExportRequestSchema(
            export_id=export.export_id,
            project_id=export.project_id,
            export_format=export.export_format,
            artifact_types=export.artifact_types,
            tags_filter=export.tags_filter,
            status=export.status,
            created_at=export.created_at,
            completed_at=export.completed_at,
            export_file_path=export.export_file_path,
            export_size_bytes=export.export_size_bytes,
        )

    except Exception as e:
        logger.error(f"Export creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export creation failed",
        )


# =====================================================================
# Health Check
# =====================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    try:
        from artifact_storage import __version__

        # Count artifacts
        from sqlalchemy import func
        stmt = select(func.count()).select_from(ArtifactRecord)
        result = await db.execute(stmt)
        artifact_count = result.scalar()

        return HealthResponse(
            status="ok",
            version=__version__,
            storage_available=True,
            database_latency_ms=0,
            redis_latency_ms=0,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed",
        )
