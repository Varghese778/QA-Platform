"""Pydantic schemas for job-related requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from orchestrator_service.models.enums import (
    JobStatus,
    TaskStatus,
    TaskType,
    Priority,
    EnvironmentTarget,
)


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------


class JobCreateRequest(BaseModel):
    """Request schema for creating a new job."""

    job_id: UUID = Field(..., description="Unique job identifier")
    story_title: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Human-readable job label",
    )
    user_story: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Raw user story text for processing",
    )
    project_id: UUID = Field(..., description="Project namespace")
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Scheduling priority",
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Classification labels",
    )
    environment_target: EnvironmentTarget = Field(
        default=EnvironmentTarget.DEV,
        description="Target environment for execution",
    )
    file_ids: List[UUID] = Field(
        default_factory=list,
        max_length=5,
        description="References to uploaded context files",
    )
    caller_id: UUID = Field(..., description="Authenticated user initiating the job")
    submitted_at: datetime = Field(..., description="Submission timestamp")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate each tag is within length limit."""
        for tag in v:
            if len(tag) > 32:
                raise ValueError(f"Tag '{tag[:20]}...' exceeds 32 character limit")
        return v


class JobListQuery(BaseModel):
    """Query parameters for listing jobs."""

    project_id: Optional[UUID] = Field(None, description="Filter by project")
    status: Optional[JobStatus] = Field(None, description="Filter by status")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------


class JobCreateResponse(BaseModel):
    """Response schema for job creation."""

    job_id: UUID
    status: JobStatus = JobStatus.QUEUED
    queued_at: datetime
    estimated_completion_seconds: int


class TaskSummary(BaseModel):
    """Summary of a task in the pipeline."""

    task_id: UUID
    task_type: TaskType
    status: TaskStatus
    retry_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TaskGraphSummary(BaseModel):
    """Summary of a task graph."""

    task_graph_id: UUID
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    progress_percent: float


class StageInfo(BaseModel):
    """Information about a pipeline stage."""

    name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobDetailResponse(BaseModel):
    """Detailed response for a single job."""

    job_id: UUID
    story_title: str
    status: JobStatus
    project_id: UUID
    caller_id: UUID
    priority: Priority
    environment_target: EnvironmentTarget
    tags: List[str] = []
    error_reason: Optional[str] = None
    stages: List[StageInfo] = []
    task_graph_summary: Optional[TaskGraphSummary] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class JobSummary(BaseModel):
    """Summary of a job for list views."""

    job_id: UUID
    story_title: str
    status: JobStatus
    project_id: UUID
    priority: Priority
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    """Response for job list queries."""

    jobs: List[JobSummary]
    total: int
    page: int
    page_size: int


class CancelResponse(BaseModel):
    """Response for job cancellation."""

    cancelled: bool
    final_status: str
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    timestamp: datetime


class ErrorDetail(BaseModel):
    """Detail of a validation error."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error_code: str
    message: str
    details: List[ErrorDetail] = []
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
