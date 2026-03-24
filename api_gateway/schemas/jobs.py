"""Job-related schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobPriority(str, Enum):
    """Job priority levels."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EnvironmentTarget(str, Enum):
    """Target environment for test execution."""

    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TestStatus(str, Enum):
    """Test case status."""

    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


# Request schemas
class JobSubmitRequest(BaseModel):
    """Request to submit a new QA job."""

    story_title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Title of the user story",
    )
    user_story: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User story description for test generation",
    )
    project_id: UUID = Field(
        ...,
        description="Project to submit the job to",
    )
    priority: JobPriority = Field(
        default=JobPriority.NORMAL,
        description="Job execution priority",
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Tags for categorization",
    )
    environment_target: EnvironmentTarget = Field(
        default=EnvironmentTarget.STAGING,
        description="Target environment for execution",
    )


# Response schemas
class JobSubmitResponse(BaseModel):
    """Response after submitting a job."""

    job_id: UUID = Field(..., description="Unique job identifier")
    queued_at: datetime = Field(..., description="Time job was queued")
    estimated_completion_seconds: Optional[int] = Field(
        None,
        description="Estimated time to completion",
    )


class StageInfo(BaseModel):
    """Information about a job stage."""

    name: str = Field(..., description="Stage name")
    status: str = Field(..., description="Stage status")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobItem(BaseModel):
    """Job item in list response."""

    job_id: UUID
    status: JobStatus
    story_title: str
    project_id: UUID
    priority: JobPriority
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: List[JobItem] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching jobs")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")


class JobDetailResponse(BaseModel):
    """Detailed job information."""

    job_id: UUID
    status: JobStatus
    story_title: str
    user_story: str
    project_id: UUID
    priority: JobPriority
    tags: List[str] = Field(default_factory=list)
    environment_target: EnvironmentTarget
    stages: List[StageInfo] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class JobCancelResponse(BaseModel):
    """Response after cancelling a job."""

    cancelled: bool = Field(..., description="Whether cancellation was successful")
    message: str = Field(..., description="Result message")


class TestCase(BaseModel):
    """Test case information."""

    test_id: UUID
    name: str
    status: TestStatus
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class JobTestsResponse(BaseModel):
    """List of test cases for a job."""

    tests: List[TestCase] = Field(default_factory=list)
    total: int


class Failure(BaseModel):
    """Test failure information."""

    test_id: UUID
    test_name: str
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None


class ReportSummary(BaseModel):
    """Report summary statistics."""

    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    coverage_percent: Optional[float] = None


class JobReportResponse(BaseModel):
    """Job execution report."""

    job_id: UUID
    summary: ReportSummary
    failures: List[Failure] = Field(default_factory=list)
    generated_at: datetime
