"""Memory Layer database models."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memory_layer.database import Base
from memory_layer.schemas.enums import (
    RecordType,
    EntityType,
    ConstraintScope,
    ConstraintPriority,
)

if TYPE_CHECKING:
    pass


class MemoryRecord(Base):
    """
    Central record in memory store.

    Represents test cases, patterns, constraints, or entities.
    """

    __tablename__ = "memory_records"

    # Primary key
    record_id: Mapped[uuid.UUID] = mapped_column(
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

    # Record metadata
    record_type: Mapped[RecordType] = mapped_column(
        Enum(RecordType, name="record_type_enum"),
        nullable=False,
        index=True,
    )

    # Content
    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Type-specific structured content",
    )

    # Tags and domains
    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(32)),
        default=list,
        comment="Classification labels",
    )
    domains: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(32)),
        default=list,
        comment="Test domain labels",
    )

    # Relationships
    embedding_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vector_entries.embedding_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Source tracking
    source_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Job that produced this record",
    )

    # Retention
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Retention expiry; null = indefinite",
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

    # Versioning
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="Optimistic concurrency counter",
    )

    # Soft delete
    archived: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        index=True,
        comment="Soft delete flag for retention",
    )

    def __repr__(self) -> str:
        return f"<MemoryRecord {self.record_id} type={self.record_type.value}>"


# Composite index for common queries
__table_args__ = (
    Index(
        "ix_memory_records_project_type_created",
        MemoryRecord.project_id,
        MemoryRecord.record_type,
        MemoryRecord.created_at.desc(),
    ),
    Index(
        "ix_memory_records_project_tags",
        MemoryRecord.project_id,
        MemoryRecord.tags,
    ),
)


class VectorEntry(Base):
    """
    Vector embedding store (mock in-memory for MVP).

    In production, would use pgvector or Pinecone.
    """

    __tablename__ = "vector_entries"

    # Primary key
    embedding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Relationship to record
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_records.record_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Project partition
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Partition key for project isolation",
    )

    # Vector embedding (stored as JSON array for MVP)
    vector: Mapped[List[float]] = mapped_column(
        JSON,
        nullable=False,
        comment="Dense embedding vector (1536 dimensions)",
    )

    # Metadata
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<VectorEntry {self.embedding_id} project={self.project_id}>"


class Entity(Base):
    """Entity node in knowledge graph."""

    __tablename__ = "entities"

    # Primary key
    entity_id: Mapped[uuid.UUID] = mapped_column(
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

    # Entity metadata
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type_enum"),
        nullable=False,
    )
    entity_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Properties
    attributes: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        comment="Key-value entity properties",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Entity {self.entity_id} name={self.entity_name}>"


class Relationship(Base):
    """Relationship edge in knowledge graph."""

    __tablename__ = "relationships"

    # Primary key
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Graph edges
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Project scoping
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Relationship type
    relationship_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g., CALLS, READS_FROM, AUTHENTICATES_WITH",
    )

    # Metadata
    relationship_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional relationship attributes",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Relationship {self.from_entity_id} -> {self.to_entity_id}>"


# Create composite index for graph queries
__table_args__ = (
    Index(
        "ix_relationships_project_from",
        Relationship.project_id,
        Relationship.from_entity_id,
    ),
    Index(
        "ix_relationships_project_to",
        Relationship.project_id,
        Relationship.to_entity_id,
    ),
)
