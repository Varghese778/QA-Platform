"""StateManager - Owns all job and task state transitions."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_service.models import (
    Job,
    Task,
    JobStatus,
    TaskStatus,
    JOB_STATE_TRANSITIONS,
    TASK_STATE_TRANSITIONS,
)

logger = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, entity_type: str, entity_id: UUID, from_state: str, to_state: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.from_state = from_state
        self.to_state = to_state
        message = (
            f"Invalid {entity_type} state transition: {from_state} -> {to_state} "
            f"for {entity_type} {entity_id}"
        )
        super().__init__(message)


class StateManager:
    """
    Manages all job and task state transitions.

    Enforces valid transition rules as defined in the PRD.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # Job State Management
    # -------------------------------------------------------------------------

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        """Get a job by ID."""
        stmt = select(Job).where(Job.job_id == job_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def transition_job(
        self,
        job: Job,
        new_status: JobStatus,
        error_reason: Optional[str] = None,
    ) -> Job:
        """
        Transition a job to a new state.

        Args:
            job: The job to transition.
            new_status: The target status.
            error_reason: Error reason (for FAILED status).

        Returns:
            The updated job.

        Raises:
            InvalidStateTransitionError: If transition is not allowed.
        """
        old_status = job.status

        # Validate transition
        allowed = JOB_STATE_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                "job", job.job_id, old_status.value, new_status.value
            )

        # Apply transition
        job.status = new_status
        job.updated_at = datetime.now(timezone.utc)

        if error_reason and new_status == JobStatus.FAILED:
            job.error_reason = error_reason

        # Set completion timestamp for terminal states
        if new_status in {JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED}:
            job.completed_at = datetime.now(timezone.utc)

        logger.info(
            f"Job {job.job_id} transitioned: {old_status.value} -> {new_status.value}"
        )

        return job

    async def set_job_processing(self, job: Job) -> Job:
        """Transition job to PROCESSING state."""
        return await self.transition_job(job, JobStatus.PROCESSING)

    async def set_job_awaiting_execution(self, job: Job) -> Job:
        """Transition job to AWAITING_EXECUTION state."""
        return await self.transition_job(job, JobStatus.AWAITING_EXECUTION)

    async def set_job_complete(self, job: Job) -> Job:
        """Transition job to COMPLETE state."""
        return await self.transition_job(job, JobStatus.COMPLETE)

    async def set_job_failed(self, job: Job, error_reason: str) -> Job:
        """Transition job to FAILED state."""
        return await self.transition_job(job, JobStatus.FAILED, error_reason)

    async def set_job_cancelled(self, job: Job) -> Job:
        """Transition job to CANCELLED state."""
        return await self.transition_job(job, JobStatus.CANCELLED)

    # -------------------------------------------------------------------------
    # Task State Management
    # -------------------------------------------------------------------------

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get a task by ID."""
        stmt = select(Task).where(Task.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def transition_task(
        self,
        task: Task,
        new_status: TaskStatus,
        error_message: Optional[str] = None,
        output_payload: Optional[dict] = None,
        assigned_agent_id: Optional[UUID] = None,
    ) -> Task:
        """
        Transition a task to a new state.

        Args:
            task: The task to transition.
            new_status: The target status.
            error_message: Error message (for FAILED status).
            output_payload: Output data (for COMPLETE status).
            assigned_agent_id: Agent ID (for RUNNING status).

        Returns:
            The updated task.

        Raises:
            InvalidStateTransitionError: If transition is not allowed.
        """
        old_status = task.status

        # Validate transition
        allowed = TASK_STATE_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                "task", task.task_id, old_status.value, new_status.value
            )

        # Apply transition
        task.status = new_status
        now = datetime.now(timezone.utc)

        # Set timestamps based on new status
        if new_status == TaskStatus.QUEUED:
            task.queued_at = now
        elif new_status == TaskStatus.RUNNING:
            task.started_at = now
            if assigned_agent_id:
                task.assigned_agent_id = assigned_agent_id
        elif new_status in {
            TaskStatus.COMPLETE,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
            TaskStatus.CANCELLED,
        }:
            task.completed_at = now

        # Set payload/error
        if error_message and new_status == TaskStatus.FAILED:
            task.error_message = error_message
        if output_payload and new_status == TaskStatus.COMPLETE:
            task.output_payload = output_payload

        logger.info(
            f"Task {task.task_id} ({task.task_type.value}) transitioned: "
            f"{old_status.value} -> {new_status.value}"
        )

        return task

    async def set_task_queued(self, task: Task) -> Task:
        """Transition task to QUEUED state."""
        return await self.transition_task(task, TaskStatus.QUEUED)

    async def set_task_running(
        self,
        task: Task,
        assigned_agent_id: Optional[UUID] = None,
    ) -> Task:
        """Transition task to RUNNING state."""
        return await self.transition_task(
            task, TaskStatus.RUNNING, assigned_agent_id=assigned_agent_id
        )

    async def set_task_complete(
        self,
        task: Task,
        output_payload: Optional[dict] = None,
    ) -> Task:
        """Transition task to COMPLETE state."""
        return await self.transition_task(
            task, TaskStatus.COMPLETE, output_payload=output_payload
        )

    async def set_task_failed(self, task: Task, error_message: str) -> Task:
        """Transition task to FAILED state."""
        return await self.transition_task(
            task, TaskStatus.FAILED, error_message=error_message
        )

    async def set_task_skipped(self, task: Task) -> Task:
        """Transition task to SKIPPED state."""
        return await self.transition_task(task, TaskStatus.SKIPPED)

    async def set_task_cancelled(self, task: Task) -> Task:
        """Transition task to CANCELLED state."""
        return await self.transition_task(task, TaskStatus.CANCELLED)

    async def retry_task(self, task: Task) -> Task:
        """
        Retry a failed task.

        Increments retry count and re-queues the task.

        Raises:
            InvalidStateTransitionError: If task cannot be retried.
        """
        if not task.can_retry():
            raise InvalidStateTransitionError(
                "task",
                task.task_id,
                task.status.value,
                "QUEUED (retry not allowed)",
            )

        task.retry_count += 1
        task.error_message = None  # Clear previous error

        logger.info(
            f"Retrying task {task.task_id} (attempt {task.retry_count}/{task.max_retries})"
        )

        return await self.transition_task(task, TaskStatus.QUEUED)
