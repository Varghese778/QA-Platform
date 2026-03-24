"""TaskGraph and Edge models - DAG structure for task dependencies."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrator_service.database import Base
from orchestrator_service.models.enums import EdgeCondition

if TYPE_CHECKING:
    from orchestrator_service.models.job import Job
    from orchestrator_service.models.task import Task


class TaskGraph(Base):
    """
    Represents a directed acyclic graph of tasks.

    The TaskGraph defines the execution order and dependencies
    between tasks in a job's pipeline.
    """

    __tablename__ = "task_graphs"

    # Primary key
    task_graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Relationship to job (one-to-one)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    job: Mapped["Job"] = relationship(
        "Job",
        back_populates="task_graph",
        foreign_keys=[job_id],
    )

    # Tasks (nodes)
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="task_graph",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Edges (dependencies) - stored separately
    edges: Mapped[List["Edge"]] = relationship(
        "Edge",
        back_populates="task_graph",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TaskGraph {self.task_graph_id} tasks={len(self.tasks)} edges={len(self.edges)}>"


class Edge(Base):
    """
    Represents a dependency edge between two tasks.

    Edges define the execution order and conditions for
    task dependencies in a TaskGraph.
    """

    __tablename__ = "edges"

    # Composite primary key
    from_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        primary_key=True,
    )
    to_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        primary_key=True,
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
        back_populates="edges",
    )

    # Condition for traversing this edge
    condition: Mapped[EdgeCondition] = mapped_column(
        Enum(EdgeCondition, name="edge_condition_enum"),
        default=EdgeCondition.ON_SUCCESS,
        nullable=False,
    )

    # Relationships to tasks
    from_task: Mapped["Task"] = relationship(
        "Task",
        foreign_keys=[from_task_id],
        lazy="joined",
    )
    to_task: Mapped["Task"] = relationship(
        "Task",
        foreign_keys=[to_task_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Edge {self.from_task_id} -> {self.to_task_id} ({self.condition.value})>"
