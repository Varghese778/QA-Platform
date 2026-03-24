"""Enum definitions for the Orchestrator Service."""

from enum import Enum


class JobStatus(str, Enum):
    """Job lifecycle states."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    AWAITING_EXECUTION = "AWAITING_EXECUTION"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    """Task lifecycle states."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class TaskType(str, Enum):
    """Types of tasks in the QA pipeline."""

    PARSE_STORY = "PARSE_STORY"
    CLASSIFY_DOMAIN = "CLASSIFY_DOMAIN"
    FETCH_CONTEXT = "FETCH_CONTEXT"
    GENERATE_TESTS = "GENERATE_TESTS"
    VALIDATE_TESTS = "VALIDATE_TESTS"
    EXECUTE_TESTS = "EXECUTE_TESTS"


class Priority(str, Enum):
    """Job priority levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EnvironmentTarget(str, Enum):
    """Target execution environment."""

    DEV = "DEV"
    STAGING = "STAGING"
    PROD = "PROD"


class EdgeCondition(str, Enum):
    """Dependency edge conditions."""

    ON_SUCCESS = "ON_SUCCESS"  # Proceed only if prerequisite succeeded
    ON_ANY = "ON_ANY"  # Proceed regardless of prerequisite status


class EventType(str, Enum):
    """State change event types."""

    JOB_QUEUED = "JOB_QUEUED"
    JOB_PROCESSING = "JOB_PROCESSING"
    JOB_AWAITING_EXECUTION = "JOB_AWAITING_EXECUTION"
    JOB_COMPLETE = "JOB_COMPLETE"
    JOB_FAILED = "JOB_FAILED"
    JOB_CANCELLED = "JOB_CANCELLED"
    TASK_QUEUED = "TASK_QUEUED"
    TASK_RUNNING = "TASK_RUNNING"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_FAILED = "TASK_FAILED"
    TASK_RETRYING = "TASK_RETRYING"


# Valid job state transitions
JOB_STATE_TRANSITIONS = {
    None: {JobStatus.QUEUED},
    JobStatus.QUEUED: {JobStatus.PROCESSING, JobStatus.CANCELLED},
    JobStatus.PROCESSING: {
        JobStatus.AWAITING_EXECUTION,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.AWAITING_EXECUTION: {
        JobStatus.COMPLETE,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    # Terminal states - no transitions allowed
    JobStatus.COMPLETE: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
}

# Valid task state transitions
TASK_STATE_TRANSITIONS = {
    None: {TaskStatus.PENDING},
    TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.CANCELLED, TaskStatus.SKIPPED},
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETE, TaskStatus.FAILED},
    TaskStatus.FAILED: {TaskStatus.QUEUED, TaskStatus.CANCELLED},  # QUEUED = retry
    # Terminal states
    TaskStatus.COMPLETE: set(),
    TaskStatus.SKIPPED: set(),
    TaskStatus.CANCELLED: set(),
}

# Priority ordering (lower = higher priority)
PRIORITY_ORDER = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}
