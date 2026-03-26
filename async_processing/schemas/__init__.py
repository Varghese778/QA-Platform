"""Schemas package - exports all Pydantic schemas."""

from async_processing.schemas.enums import (
    EventType,
    EventStatus,
    EventPriority,
    ConnectionStatus,
)
from async_processing.schemas.tasks import (
    EventPayload,
    EventRequest,
    EventBatchRequest,
    EventResponse,
    EventRecord,
    WebSocketMessage,
    JobStatusUpdate,
    DeadLetterEntry,
    ReplayRequest,
    WebSocketSessionRecord,
    HealthResponse,
    EventHistoryResponse,
    ErrorDetail,
)

__all__ = [
    # Enums
    "EventType",
    "EventStatus",
    "EventPriority",
    "ConnectionStatus",
    # Requests/Responses
    "EventPayload",
    "EventRequest",
    "EventBatchRequest",
    "EventResponse",
    "EventRecord",
    "WebSocketMessage",
    "JobStatusUpdate",
    "DeadLetterEntry",
    "ReplayRequest",
    "WebSocketSessionRecord",
    "HealthResponse",
    "EventHistoryResponse",
    "ErrorDetail",
]
