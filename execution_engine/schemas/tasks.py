"""Pydantic schemas for Execution Engine."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from execution_engine.schemas.enums import (
    ExecutionStatus,
    TestResultStatus,
    TestEnvironment,
)


# =====================================================================
# Execution Request/Response Schemas
# =====================================================================


class ExecutionRequest(BaseModel):
    """Request to execute a test suite."""

    project_id: UUID
    job_id: UUID
    test_suite_id: UUID
    test_cases: List[Dict[str, Any]] = Field(
        ..., description="Array of test case definitions"
    )
    environment: TestEnvironment = Field(default=TestEnvironment.UNIT)
    timeout_seconds: Optional[int] = None
    variables: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None


class ExecutionResponse(BaseModel):
    """Response after accepting an execution."""

    execution_id: UUID
    status: ExecutionStatus
    created_at: datetime


# =====================================================================
# Test Result Schemas
# =====================================================================


class TestStepResult(BaseModel):
    """Result of a single test step."""

    step_number: int
    action: str
    status: TestResultStatus
    duration_seconds: float
    error_message: Optional[str] = None
    output: Optional[str] = None


class TestCaseResult(BaseModel):
    """Result of a single test case."""

    test_case_id: Optional[UUID] = None
    test_name: str
    status: TestResultStatus
    duration_seconds: float
    error_message: Optional[str] = None
    steps: List[TestStepResult] = Field(default_factory=list)
    retry_count: int = 0
    is_flaky: bool = False


# =====================================================================
# Execution Record Schemas
# =====================================================================


class ExecutionRecord(BaseModel):
    """Full execution record."""

    execution_id: UUID
    project_id: UUID
    job_id: UUID
    test_suite_id: UUID
    status: ExecutionStatus
    environment: TestEnvironment
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    skipped_tests: int
    flaky_tests: int
    total_duration_seconds: float
    coverage_percentage: float
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    version: int


class ExecutionReport(BaseModel):
    """Execution report with test results."""

    execution_id: UUID
    status: ExecutionStatus
    summary: str
    total_tests: int
    passed_count: int
    failed_count: int
    error_count: int
    flaky_count: int
    total_duration_seconds: float
    coverage_percentage: float
    test_results: List[TestCaseResult]
    created_at: datetime


class ExecutionListResponse(BaseModel):
    """Response for listing executions."""

    executions: List[ExecutionRecord]
    total_count: int
    limit: int
    offset: int


class CancelExecutionRequest(BaseModel):
    """Request to cancel an execution."""

    reason: Optional[str] = None


class CancelExecutionResponse(BaseModel):
    """Response after cancellation."""

    execution_id: UUID
    status: ExecutionStatus
    cancelled_at: datetime


# =====================================================================
# Runner / Health Schemas
# =====================================================================


class RunnerInstanceSchema(BaseModel):
    """Runner instance information."""

    runner_id: UUID
    status: str
    container_id: Optional[str] = None
    last_heartbeat: datetime
    active_execution_id: Optional[UUID] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    active_executions: int = 0
    available_runners: int = 0
    queue_depth: int = 0
    database_latency_ms: int = 0
    redis_latency_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    """Error detail response."""

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
