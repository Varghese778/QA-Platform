"""WriteHandler - Validates payloads and writes records."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import jsonschema
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from memory_layer.config import get_settings
from memory_layer.models import MemoryRecord, VectorEntry
from memory_layer.schemas import (
    RecordType,
    TestCasePayload,
    PatternPayload,
    ConstraintPayload,
    EntityPayload,
    TestDomain,
)
from memory_layer.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)
settings = get_settings()


class PayloadValidationError(Exception):
    """Raised when payload validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class WriteHandler:
    """
    Validates and persists memory records.

    1. Validate payload against schema
    2. Generate embedding for searchability
    3. Persist record and embedding
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
    ):
        self.db = db
        self.embedding_service = embedding_service

    async def write_record(
        self,
        project_id: UUID,
        record_type: RecordType,
        payload: Dict[str, Any],
        tags: Optional[list] = None,
        domains: Optional[list[TestDomain]] = None,
        source_job_id: Optional[UUID] = None,
        expires_at: Optional[datetime] = None,
    ) -> UUID:
        """
        Write a record to memory.

        Args:
            project_id: Project owning this record.
            record_type: Type of record.
            payload: Type-specific payload.
            tags: Classification tags.
            domains: Test domains.
            source_job_id: Job that produced this record.
            expires_at: Retention expiry time.

        Returns:
            The created record_id.

        Raises:
            PayloadValidationError: If payload is invalid.
        """
        # Validate payload size
        import json
        payload_json = json.dumps(payload)
        if len(payload_json) > settings.max_payload_size_bytes:
            raise PayloadValidationError(
                f"Payload exceeds {settings.max_payload_size_bytes} bytes"
            )

        # Validate payload schema
        self._validate_payload(record_type, payload)

        # Generate embedding for searchability
        embedding_vector = await self._generate_embedding(payload)

        # Create record
        record_id = UUID(int=0)  # Will be auto-generated
        record = MemoryRecord(
            project_id=project_id,
            record_type=record_type,
            payload=payload,
            tags=tags or [],
            domains=[d.value if isinstance(d, TestDomain) else d for d in (domains or [])],
            source_job_id=source_job_id,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(record)
        await self.db.flush()

        # Create vector entry
        vector_entry = VectorEntry(
            record_id=record.record_id,
            project_id=project_id,
            vector=embedding_vector,
        )
        self.db.add(vector_entry)
        record.embedding_id = vector_entry.embedding_id

        await self.db.flush()

        logger.info(
            f"Wrote record {record.record_id} (type={record_type.value}) "
            f"for project {project_id}"
        )

        return record.record_id

    def _validate_payload(self, record_type: RecordType, payload: Dict[str, Any]) -> None:
        """
        Validate payload against schema for the record type.

        Raises:
            PayloadValidationError: If validation fails.
        """
        try:
            if record_type == RecordType.TEST_CASE:
                TestCasePayload.model_validate(payload)
            elif record_type == RecordType.PATTERN:
                PatternPayload.model_validate(payload)
            elif record_type == RecordType.CONSTRAINT:
                ConstraintPayload.model_validate(payload)
            elif record_type == RecordType.ENTITY:
                EntityPayload.model_validate(payload)
            else:
                raise PayloadValidationError(f"Unknown record type: {record_type}")
        except ValidationError as e:
            raise PayloadValidationError(f"Payload validation failed: {str(e)}")

    async def _generate_embedding(self, payload: Dict[str, Any]) -> list[float]:
        """
        Generate embedding for a payload.

        Extracts text representation and embeds.
        """
        # Flatten payload to text
        text_parts = []

        # Extract text based on record type (heuristic)
        if "title" in payload:
            text_parts.append(payload["title"])
        if "description" in payload:
            text_parts.append(payload["description"])
        if "pattern_name" in payload:
            text_parts.append(payload["pattern_name"])
        if "constraint_name" in payload:
            text_parts.append(payload["constraint_name"])
        if "rule" in payload:
            text_parts.append(payload["rule"])
        if "entity_name" in payload:
            text_parts.append(payload["entity_name"])

        # If no text extracted, use full payload JSON
        if not text_parts:
            import json
            text_parts.append(json.dumps(payload)[:500])  # Truncate

        text = " ".join(text_parts)
        return await self.embedding_service.embed_text(text)

    async def update_record(
        self,
        record_id: UUID,
        project_id: UUID,
        payload: Optional[Dict[str, Any]] = None,
        tags: Optional[list] = None,
        domains: Optional[list] = None,
    ) -> None:
        """
        Update an existing record.

        Args:
            record_id: Record to update.
            project_id: Project owning the record.
            payload: Updated payload.
            tags: Updated tags.
            domains: Updated domains.
        """
        from sqlalchemy import select

        # Get record
        stmt = select(MemoryRecord).where(
            MemoryRecord.record_id == record_id,
            MemoryRecord.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise PayloadValidationError(f"Record {record_id} not found in project {project_id}")

        # Update fields
        if payload is not None:
            self._validate_payload(record.record_type, payload)
            record.payload = payload

            # Regenerate embedding
            embedding_vector = await self._generate_embedding(payload)
            if record.embedding_id:
                stmt_vec = select(VectorEntry).where(
                    VectorEntry.embedding_id == record.embedding_id
                )
                result_vec = await self.db.execute(stmt_vec)
                vec_entry = result_vec.scalar_one()
                vec_entry.vector = embedding_vector

        if tags is not None:
            record.tags = tags

        if domains is not None:
            record.domains = [d.value if isinstance(d, TestDomain) else d for d in domains]

        record.updated_at = datetime.now(timezone.utc)
        record.version += 1

        logger.info(f"Updated record {record_id}")
