"""CancellationHandler - Handles job cancellation requests."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_service.models import Job, TaskGraph, Task, JobStatus, TaskStatus
from orchestrator_service.services.state_manager import StateManager
from orchestrator_service.services.dependency_resolver import DependencyResolver

logger = logging.getLogger(__name__)


class CancellationError(Exception):
    """Raised when cancellation fails."""

    def __init__(self, job_id: UUID, message: str):
        self.job_id = job_id
        self.message = message
        super().__init__(f"Cancellation failed for job {job_id}: {message}")


class CancellationHandler:
    """
    Handles job cancellation requests.

    Stops scheduling, drains in-flight tasks, and marks job CANCELLED.
    """

    def __init__(
        self,
        db: AsyncSession,
        state_manager: StateManager,
        dependency_resolver: DependencyResolver,
    ):
        self.db = db
        self.state_manager = state_manager
        self.dependency_resolver = dependency_resolver

    async def cancel_job(
        self,
        job: Job,
        caller_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> Job:
        """
        Cancel a job and all its pending tasks.

        Args:
            job: The job to cancel.
            caller_id: ID of user requesting cancellation.
            reason: Optional cancellation reason.

        Returns:
            The cancelled job.

        Raises:
            CancellationError: If job cannot be cancelled.
        """
        # Validate job can be cancelled
        if not job.can_cancel():
            raise CancellationError(
                job.job_id,
                f"Cannot cancel job in {job.status.value} status",
            )

        # Optional: Validate caller owns the job
        if caller_id and job.caller_id != caller_id:
            raise CancellationError(
                job.job_id,
                "Only the job owner can cancel it",
            )

        logger.info(f"Cancelling job {job.job_id}, reason: {reason or 'user requested'}")

        # Cancel all pending/queued tasks
        if job.task_graph_id:
            await self._cancel_tasks(job.task_graph_id)

        # Transition job to CANCELLED
        await self.state_manager.set_job_cancelled(job)

        if reason:
            job.error_reason = f"Cancelled: {reason}"

        logger.info(f"Job {job.job_id} cancelled successfully")

        return job

    async def _cancel_tasks(self, task_graph_id: UUID) -> int:
        """
        Cancel all pending and queued tasks in a graph.

        Running tasks are left to complete (or timeout).

        Returns number of tasks cancelled.
        """
        stmt = select(Task).where(
            Task.task_graph_id == task_graph_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.QUEUED]),
        )
        result = await self.db.execute(stmt)
        tasks = result.scalars().all()

        cancelled_count = 0
        for task in tasks:
            try:
                await self.state_manager.set_task_cancelled(task)
                cancelled_count += 1
            except Exception as e:
                logger.error(f"Failed to cancel task {task.task_id}: {e}")

        logger.info(f"Cancelled {cancelled_count} tasks in graph {task_graph_id}")
        return cancelled_count

    async def can_cancel(self, job: Job, caller_id: Optional[UUID] = None) -> tuple[bool, str]:
        """
        Check if a job can be cancelled.

        Returns:
            Tuple of (can_cancel, reason).
        """
        if job.is_terminal():
            return False, f"Job is already in terminal state: {job.status.value}"

        if not job.can_cancel():
            return False, f"Job cannot be cancelled in {job.status.value} status"

        if caller_id and job.caller_id != caller_id:
            return False, "Only the job owner can cancel it"

        return True, "OK"

    async def abort_execution(self, job: Job) -> bool:
        """
        Abort execution for a job in AWAITING_EXECUTION state.

        Signals the Execution Engine to stop the test run.
        """
        if job.status != JobStatus.AWAITING_EXECUTION:
            return False

        # MVP: Mock abort signal
        logger.info(f"[MOCK] Sending abort signal to Execution Engine for job {job.job_id}")

        # In production:
        # async with httpx.AsyncClient() as client:
        #     await client.post(
        #         f"{settings.execution_engine_url}/internal/v1/executions/{job.job_id}/abort"
        #     )

        return True
