"""Async Processing database models."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from async_processing.database import Base
from async_processing.schemas.enums import (
    EventType,
    EventStatus,
    EventPriority,
    ConnectionStatus,
)


class EventRecord(Base):
    """
    Central event record for all system events.

    Tracks every event produced by services with delivery status.
    """

    __tablename__ = "event_records"

    # Primary key
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Ownership & context
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Project namespace",
    )

    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Associated job (if applicable)",
    )

    # Event details
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type_enum"),
        nullable=False,
        index=True,
    )

    source_service: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Service that produced the event",
    )

    priority: Mapped[EventPriority] = mapped_column(
        Enum(EventPriority, name="event_priority_enum"),
        default=EventPriority.NORMAL,
        nullable=False,
    )

    # Status tracking
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status_enum"),
        default=EventStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Event data
    data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Event payload",
    )

    context: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional context like trace IDs",
    )

    # Delivery tracking
    retry_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<EventRecord {self.event_id} type={self.event_type.value}>"


class WebSocketSession(Base):
    """
    WebSocket session registry.

    Tracks active WebSocket connections for real-time updates.
    """

    __tablename__ = "websocket_sessions"

    # Primary key
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Job being monitored",
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Client identification
    client_id: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="Client identifier (e.g., browser session ID)",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="CONNECTED",
        nullable=False,
        comment="CONNECTED, DISCONNECTED, ERROR",
    )

    # Lifecycle
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    disconnected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<WebSocketSession {self.session_id} job={self.job_id}>"


class DeadLetterEntry(Base):
    """
    Dead letter queue for failed events.

    Stores events that failed to be processed for later replay.
    """

    __tablename__ = "dead_letter_entries"

    # Primary key
    dlq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference to original event
    original_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Ownership
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Event metadata
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type_enum"),
        nullable=False,
    )

    # Failure details
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for dead lettering",
    )

    retry_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Original event data
    data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    last_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<DeadLetterEntry {self.dlq_id}>"


class EventDeliveryLog(Base):
    """
    Log of event delivery attempts.

    Tracks each delivery attempt for auditing and debugging.
    """

    __tablename__ = "event_delivery_logs"

    # Primary key
    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Delivery attempt details
    attempt_number: Mapped[int] = mapped_column(
        nullable=False,
    )

    success: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    status_code: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    duration_ms: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Timestamp
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<EventDeliveryLog {self.log_id}>"


# Composite indexes
__table_args__ = (
    Index(
        "ix_event_records_project_type_created",
        EventRecord.project_id,
        EventRecord.event_type,
        EventRecord.created_at.desc(),
    ),
    Index(
        "ix_event_records_job_created",
        EventRecord.job_id,
        EventRecord.created_at.desc(),
    ),
    Index(
        "ix_websocket_sessions_job_status",
        WebSocketSession.job_id,
        WebSocketSession.status,
    ),
    Index(
        "ix_dead_letter_entries_project_created",
        DeadLetterEntry.project_id,
        DeadLetterEntry.created_at.desc(),
    ),
    Index(
        "ix_event_delivery_logs_event_attempted",
        EventDeliveryLog.event_id,
        EventDeliveryLog.attempted_at.desc(),
    ),
)
