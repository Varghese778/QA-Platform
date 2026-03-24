"""Task model - represents a single task in the pipeline."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrator_service.database import Base
from orchestrator_service.models.enums import TaskStatus, TaskType

if TYPE_CHECKING:
    from orchestrator_service.models.task_graph import TaskGraph


class Task(Base):
    """
    Represents a single task in the QA pipeline.

    Tasks are nodes in a TaskGraph and execute a specific
    operation (e.g., PARSE_STORY, GENERATE_TESTS).
    """

    __tablename__ = "tasks"

    # Primary key
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Relationship to graph
    task_graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_graphs.task_graph_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_graph: Mapped["TaskGraph"] = relationship(
        "TaskGraph",
        back_populates="tasks",
    )

    # Task type and status
    task_type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, name="task_type_enum"),
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status_enum"),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Assignment
    assigned_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Agent handling this task",
    )

    # Payloads
    input_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        comment="Task-specific input data",
    )
    output_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Task-specific output data; populated on COMPLETE",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Populated on FAILED",
    )

    # Retry configuration
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of retry attempts made",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Maximum allowed retries",
    )

    # Timeout
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=300,
        nullable=False,
        comment="Per-task timeout",
    )

    # Timestamps
    queued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Time enqueued to agent",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Agent pickup time",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Task terminal state time",
    )

    def __repr__(self) -> str:
        return f"<Task {self.task_id} type={self.task_type.value} status={self.status.value}>"

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in {
            TaskStatus.COMPLETE,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
            TaskStatus.CANCELLED,
        }

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.status == TaskStatus.FAILED and self.retry_count < self.max_retries

    def get_backoff_seconds(self) -> int:
        """Calculate exponential backoff for retry."""
        # Backoff: 5s, 15s, 45s (5 * 3^retry_count)
        return 5 * (3 ** self.retry_count)
