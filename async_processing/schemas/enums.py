"""Enum definitions for Async Processing."""

from enum import Enum


class EventType(str, Enum):
    """Types of events in the system."""

    JOB_CREATED = "JOB_CREATED"
    JOB_QUEUED = "JOB_QUEUED"
    JOB_STARTED = "JOB_STARTED"
    JOB_PROGRESSED = "JOB_PROGRESSED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    JOB_CANCELLED = "JOB_CANCELLED"

    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_TEST_PASSED = "EXECUTION_TEST_PASSED"
    EXECUTION_TEST_FAILED = "EXECUTION_TEST_FAILED"
    EXECUTION_TEST_FLAKY = "EXECUTION_TEST_FLAKY"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"

    ARTIFACT_UPLOADED = "ARTIFACT_UPLOADED"
    ARTIFACT_SCANNED = "ARTIFACT_SCANNED"
    ARTIFACT_DELETED = "ARTIFACT_DELETED"

    MEMORY_INDEXED = "MEMORY_INDEXED"


class EventStatus(str, Enum):
    """Status of an event in the system."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"


class EventPriority(str, Enum):
    """Event priority for processing."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConnectionStatus(str, Enum):
    """WebSocket connection status."""

    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
