"""Enum definitions for the Multi-Agent Engine."""

from enum import Enum


class TaskType(str, Enum):
    """Types of tasks handled by agents."""

    PARSE_STORY = "PARSE_STORY"
    CLASSIFY_DOMAIN = "CLASSIFY_DOMAIN"
    FETCH_CONTEXT = "FETCH_CONTEXT"
    GENERATE_TESTS = "GENERATE_TESTS"
    VALIDATE_TESTS = "VALIDATE_TESTS"
    ANALYSE_COVERAGE = "ANALYSE_COVERAGE"


class TaskStatus(str, Enum):
    """Task queue entry status."""

    WAITING = "WAITING"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class AgentStatus(str, Enum):
    """Agent instance status."""

    IDLE = "IDLE"
    BUSY = "BUSY"
    DRAINING = "DRAINING"
    OFFLINE = "OFFLINE"


class Priority(str, Enum):
    """Task scheduling priority."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TestType(str, Enum):
    """Types of test cases."""

    FUNCTIONAL = "FUNCTIONAL"
    BOUNDARY = "BOUNDARY"
    NEGATIVE = "NEGATIVE"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"


class TestPriority(str, Enum):
    """Test case priority levels."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class TestDomain(str, Enum):
    """Test domain classifications."""

    UI = "UI"
    API = "API"
    DATABASE = "DATABASE"
    AUTH = "AUTH"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"


class FailureCategory(str, Enum):
    """Categories of task failures."""

    TIMEOUT = "TIMEOUT"
    OUTPUT_PARSE_ERROR = "OUTPUT_PARSE_ERROR"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    LLM_API_ERROR = "LLM_API_ERROR"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CONTEXT_TOO_LARGE = "CONTEXT_TOO_LARGE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Priority score mapping (lower = higher priority)
PRIORITY_SCORES = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1000,
    Priority.MEDIUM: 2000,
    Priority.LOW: 3000,
}
