"""Task schemas for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from multi_agent_engine.schemas.enums import (
    TaskType,
    TaskStatus,
    AgentStatus as AgentStatusEnum,
    Priority,
)


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------


class ModelConfig(BaseModel):
    """LLM model configuration overrides."""

    model: Optional[str] = Field(None, description="Model identifier override")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)


class TaskCreateRequest(BaseModel):
    """Request schema for creating a new task."""

    task_id: UUID = Field(..., description="Unique task identifier from Orchestrator")
    task_type: TaskType = Field(..., description="Agent routing key")
    job_id: UUID = Field(..., description="Parent job context")
    project_id: UUID = Field(..., description="Project scope for memory and logging")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Task-specific input data"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Pre-fetched memory context"
    )
    priority: Priority = Field(default=Priority.MEDIUM, description="Task priority")
    timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=600,
        description="Maximum execution time",
    )
    retry_attempt: int = Field(
        default=0, ge=0, le=3, description="Retry sequence number"
    )
    model_config_override: Optional[ModelConfig] = Field(
        None, alias="model_config", description="LLM config overrides"
    )

    @field_validator("context")
    @classmethod
    def validate_context_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate context size is within limits."""
        import json
        serialized = json.dumps(v)
        if len(serialized) > 32768:  # 32 KB
            raise ValueError("Context exceeds maximum size of 32 KB")
        return v

    model_config = {"populate_by_name": True}


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------


class TaskAcceptedResponse(BaseModel):
    """Response when task is accepted into queue."""

    task_id: UUID
    accepted: bool = True
    queued_at: datetime


class TaskStatusResponse(BaseModel):
    """Response for task status query."""

    task_id: UUID
    status: TaskStatus
    agent_id: Optional[UUID] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AgentStatusResponse(BaseModel):
    """Status of a single agent instance."""

    agent_id: UUID
    agent_type: TaskType
    status: AgentStatusEnum
    current_task_id: Optional[UUID] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_heartbeat: datetime


class AgentListResponse(BaseModel):
    """List of all agent statuses."""

    agents: List[AgentStatusResponse]


class QueueDepthResponse(BaseModel):
    """Queue depth information."""

    task_type: TaskType
    depth: int
    oldest_queued_at: Optional[datetime] = None


class TaskResultPayload(BaseModel):
    """Payload sent to Orchestrator on task completion."""

    task_id: UUID
    job_id: UUID
    status: TaskStatus
    output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    agent_id: UUID
    model_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    completed_at: datetime


# -----------------------------------------------------------------------------
# Internal Queue Entry
# -----------------------------------------------------------------------------


class TaskQueueEntry(BaseModel):
    """Internal representation of a queued task."""

    queue_id: UUID
    task_id: UUID
    task_type: TaskType
    job_id: UUID
    project_id: UUID
    payload: Dict[str, Any]
    context: Dict[str, Any]
    priority: Priority
    priority_score: int
    timeout_seconds: int
    retry_attempt: int
    model_config_data: Optional[Dict[str, Any]] = None
    enqueued_at: datetime
    dequeued_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.WAITING

    model_config = {"arbitrary_types_allowed": True}


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    timestamp: datetime
    agents_online: int = 0
    total_queue_depth: int = 0


class ErrorResponse(BaseModel):
    """Standard error response."""

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
