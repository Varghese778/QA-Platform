"""Enum definitions for Execution Engine."""

from enum import Enum


class ExecutionStatus(str, Enum):
    """Execution lifecycle status."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class TestResultStatus(str, Enum):
    """Individual test result status."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    FLAKY = "FLAKY"


class RunnerStatus(str, Enum):
    """Runner instance status."""

    IDLE = "IDLE"
    BUSY = "BUSY"
    UNHEALTHY = "UNHEALTHY"
    OFFLINE = "OFFLINE"


class TestEnvironment(str, Enum):
    """Test execution environment."""

    UNIT = "UNIT"
    INTEGRATION = "INTEGRATION"
    E2E = "E2E"
    PERFORMANCE = "PERFORMANCE"
