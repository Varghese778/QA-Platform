"""TimeoutWatchdog - Monitors per-task and per-job timeouts."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_service.config import get_settings
from orchestrator_service.models import Job, Task, TaskGraph, JobStatus, TaskStatus
from orchestrator_service.services.state_manager import StateManager

logger = logging.getLogger(__name__)
settings = get_settings()


class TimeoutWatchdog:
    """
    Monitors per-task and per-job timeouts.

    Runs periodic checks and triggers failures on timeout breaches.
    """

    def __init__(self, db: AsyncSession, state_manager: StateManager):
        self.db = db
        self.state_manager = state_manager
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the watchdog background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("TimeoutWatchdog started")

    async def stop(self) -> None:
        """Stop the watchdog background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("TimeoutWatchdog stopped")

    async def _run_loop(self) -> None:
        """Main watchdog loop."""
        while self._running:
            try:
                await self._check_timeouts()
            except Exception as e:
                logger.error(f"Error in timeout check: {e}")

            await asyncio.sleep(settings.watchdog_check_interval_seconds)

    async def _check_timeouts(self) -> None:
        """Check for timed out tasks and jobs."""
        await self._check_task_timeouts()
        await self._check_job_timeouts()

    async def _check_task_timeouts(self) -> None:
        """Check for tasks that have exceeded their timeout."""
        now = datetime.now(timezone.utc)

        # Find running tasks
        stmt = select(Task).where(Task.status == TaskStatus.RUNNING)
        result = await self.db.execute(stmt)
        running_tasks = result.scalars().all()

        for task in running_tasks:
            if task.started_at:
                elapsed = (now - task.started_at).total_seconds()
                if elapsed > task.timeout_seconds:
                    logger.warning(
                        f"Task {task.task_id} ({task.task_type.value}) timed out "
                        f"after {elapsed:.1f}s (limit: {task.timeout_seconds}s)"
                    )
                    await self.state_manager.set_task_failed(
                        task,
                        f"Task timed out after {task.timeout_seconds} seconds",
                    )

    async def _check_job_timeouts(self) -> None:
        """Check for jobs that have exceeded their global timeout."""
        now = datetime.now(timezone.utc)
        job_timeout = settings.default_job_timeout_seconds

        # Find active jobs
        stmt = select(Job).where(
            Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.AWAITING_EXECUTION])
        )
        result = await self.db.execute(stmt)
        active_jobs = result.scalars().all()

        for job in active_jobs:
            elapsed = (now - job.created_at).total_seconds()
            if elapsed > job_timeout:
                logger.warning(
                    f"Job {job.job_id} timed out after {elapsed:.1f}s "
                    f"(limit: {job_timeout}s)"
                )
                await self.state_manager.set_job_failed(
                    job,
                    f"Job timed out after {job_timeout} seconds",
                )

    async def check_single_task(self, task: Task) -> bool:
        """
        Check if a specific task has timed out.

        Returns True if the task timed out and was marked failed.
        """
        if task.status != TaskStatus.RUNNING or not task.started_at:
            return False

        now = datetime.now(timezone.utc)
        elapsed = (now - task.started_at).total_seconds()

        if elapsed > task.timeout_seconds:
            await self.state_manager.set_task_failed(
                task,
                f"Task timed out after {task.timeout_seconds} seconds",
            )
            return True

        return False

    async def get_stale_tasks(self, stale_threshold_seconds: int = 300) -> List[Task]:
        """
        Get tasks that appear to be stale (RUNNING but no updates).

        Args:
            stale_threshold_seconds: Time without updates to consider stale.

        Returns:
            List of potentially stale tasks.
        """
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(seconds=stale_threshold_seconds)

        stmt = select(Task).where(
            Task.status == TaskStatus.RUNNING,
            Task.started_at < threshold,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
