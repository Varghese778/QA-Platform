"""Pydantic schemas for Async Processing."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from async_processing.schemas.enums import (
    EventType,
    EventStatus,
    EventPriority,
    ConnectionStatus,
)


# =====================================================================
# Event Schemas
# =====================================================================


class EventPayload(BaseModel):
    """Base event payload with context."""

    event_type: EventType
    source_service: str = Field(..., description="Service that produced the event")
    timestamp: datetime
    data: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, str]] = None


class EventRequest(BaseModel):
    """Request to ingest a single event."""

    project_id: UUID
    job_id: Optional[UUID] = None
    event_type: EventType
    source_service: str
    data: Dict[str, Any] = Field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    context: Optional[Dict[str, str]] = None


class EventBatchRequest(BaseModel):
    """Request to ingest multiple events."""

    events: List[EventRequest] = Field(..., min_length=1)


class EventResponse(BaseModel):
    """Response after ingesting an event."""

    event_id: UUID
    status: EventStatus
    created_at: datetime


class EventRecord(BaseModel):
    """Full event record."""

    event_id: UUID
    project_id: UUID
    job_id: Optional[UUID] = None
    event_type: EventType
    source_service: str
    status: EventStatus
    priority: EventPriority
    data: Dict[str, Any]
    context: Optional[Dict[str, str]] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    version: int = 1


# =====================================================================
# WebSocket Message Schemas
# =====================================================================


class WebSocketMessage(BaseModel):
    """Message sent over WebSocket."""

    message_type: str = Field(...)  # "status_update", "error", "heartbeat"
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class JobStatusUpdate(BaseModel):
    """Job status update event for WebSocket."""

    job_id: UUID
    status: str
    progress_percent: Optional[int] = None
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =====================================================================
# Dead Letter Schemas
# =====================================================================


class DeadLetterEntry(BaseModel):
    """Dead letter queue entry."""

    dlq_id: UUID
    original_event_id: UUID
    project_id: UUID
    job_id: Optional[UUID] = None
    event_type: EventType
    reason: str
    retry_count: int
    data: Dict[str, Any]
    created_at: datetime
    last_retry_at: Optional[datetime] = None


class ReplayRequest(BaseModel):
    """Request to replay dead letter events."""

    dlq_ids: List[UUID] = Field(..., min_length=1)


# =====================================================================
# Connection Registry Schemas
# =====================================================================


class WebSocketSessionRecord(BaseModel):
    """WebSocket session information."""

    session_id: UUID
    job_id: UUID
    project_id: UUID
    client_id: Optional[str] = None
    status: ConnectionStatus
    connected_at: datetime
    disconnected_at: Optional[datetime] = None
    last_heartbeat: datetime


# =====================================================================
# Health & Response Schemas
# =====================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    active_connections: int = 0
    pending_events: int = 0
    dead_letter_count: int = 0
    database_latency_ms: int = 0
    redis_latency_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EventHistoryResponse(BaseModel):
    """Response for event history query."""

    job_id: UUID
    events: List[EventRecord]
    total_count: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    """Error detail response."""

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
