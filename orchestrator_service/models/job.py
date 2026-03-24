"""Job model - represents a QA pipeline job."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrator_service.database import Base
from orchestrator_service.models.enums import EnvironmentTarget, JobStatus, Priority

if TYPE_CHECKING:
    from orchestrator_service.models.task_graph import TaskGraph


class Job(Base):
    """
    Represents a QA pipeline job.

    A job tracks the end-to-end processing of a user story
    through the QA pipeline.
    """

    __tablename__ = "jobs"

    # Primary key
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Job content
    story_title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Human-readable job label",
    )
    user_story: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Original user story text",
    )

    # Ownership and context
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Project namespace",
    )
    caller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Submitting user",
    )

    # Configuration
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum"),
        default=Priority.MEDIUM,
        nullable=False,
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(32)),
        default=list,
        comment="Classification labels",
    )
    environment_target: Mapped[EnvironmentTarget] = mapped_column(
        Enum(EnvironmentTarget, name="environment_target_enum"),
        default=EnvironmentTarget.DEV,
        nullable=False,
    )
    file_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        default=list,
        comment="Attached context file references",
    )

    # Status
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum"),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    error_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Populated on FAILED status",
    )

    # Relationships
    task_graph_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_graphs.task_graph_id", ondelete="SET NULL"),
        nullable=True,
    )
    task_graph: Mapped[Optional["TaskGraph"]] = relationship(
        "TaskGraph",
        back_populates="job",
        uselist=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Terminal state timestamp",
    )

    def __repr__(self) -> str:
        return f"<Job {self.job_id} status={self.status.value}>"

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in {JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED}

    def can_cancel(self) -> bool:
        """Check if job can be cancelled."""
        return self.status in {JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.AWAITING_EXECUTION}
