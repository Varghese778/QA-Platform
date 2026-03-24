"""TaskScheduler - Submits ready tasks to Multi-Agent Engine queue."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_service.config import get_settings
from orchestrator_service.models import Task, TaskGraph, Priority, TaskStatus, PRIORITY_ORDER
from orchestrator_service.services.state_manager import StateManager

logger = logging.getLogger(__name__)
settings = get_settings()


class TaskScheduleError(Exception):
    """Raised when task scheduling fails."""

    def __init__(self, task_id: UUID, message: str):
        self.task_id = task_id
        self.message = message
        super().__init__(f"Failed to schedule task {task_id}: {message}")


class TaskScheduler:
    """
    Submits ready tasks to the Multi-Agent Engine queue.

    Handles priority ordering, context assembly, and retry logic.
    """

    def __init__(
        self,
        db: AsyncSession,
        state_manager: StateManager,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.db = db
        self.state_manager = state_manager
        self._http_client = http_client

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=settings.http_client_timeout_seconds
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def schedule_tasks(
        self,
        tasks: List[Task],
        priority: Priority = Priority.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Task]:
        """
        Schedule multiple tasks for execution.

        Tasks are sorted by priority before scheduling.

        Args:
            tasks: List of tasks to schedule.
            priority: Job-level priority.
            context: Additional context to inject.

        Returns:
            List of successfully scheduled tasks.
        """
        if not tasks:
            return []

        # Sort by priority (lower number = higher priority)
        sorted_tasks = sorted(
            tasks,
            key=lambda t: PRIORITY_ORDER.get(priority, 2),
        )

        scheduled = []
        for task in sorted_tasks:
            try:
                await self.schedule_task(task, priority, context)
                scheduled.append(task)
            except TaskScheduleError as e:
                logger.error(f"Failed to schedule task: {e}")
                # Continue scheduling other tasks

        return scheduled

    async def schedule_task(
        self,
        task: Task,
        priority: Priority = Priority.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Schedule a single task for execution.

        Args:
            task: The task to schedule.
            priority: Job-level priority.
            context: Additional context to inject.

        Returns:
            The scheduled task.

        Raises:
            TaskScheduleError: If scheduling fails.
        """
        if task.status != TaskStatus.PENDING:
            raise TaskScheduleError(
                task.task_id,
                f"Task must be in PENDING status, got {task.status.value}",
            )

        # Build task payload for Multi-Agent Engine
        payload = self._build_enqueue_payload(task, priority, context)

        try:
            # Send to Multi-Agent Engine queue
            await self._enqueue_task(payload)

            # Transition to QUEUED
            await self.state_manager.set_task_queued(task)

            logger.info(
                f"Scheduled task {task.task_id} ({task.task_type.value}) "
                f"with priority {priority.value}"
            )

            return task

        except httpx.HTTPError as e:
            raise TaskScheduleError(task.task_id, f"HTTP error: {str(e)}")
        except Exception as e:
            raise TaskScheduleError(task.task_id, str(e))

    def _build_enqueue_payload(
        self,
        task: Task,
        priority: Priority,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the payload for the Multi-Agent Engine queue."""
        return {
            "task_id": str(task.task_id),
            "task_type": task.task_type.value,
            "payload": task.input_payload or {},
            "priority": priority.value,
            "context": context or {},
            "timeout_seconds": task.timeout_seconds,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
        }

    async def _enqueue_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send task to Multi-Agent Engine queue.

        For MVP, this mocks the enqueue operation.
        In production, this would call the actual service.
        """
        # MVP: Mock the enqueue operation
        logger.info(f"[MOCK] Enqueueing task {payload['task_id']} to Multi-Agent Engine")

        # In production, uncomment:
        # client = await self.get_http_client()
        # response = await client.post(
        #     f"{settings.multi_agent_engine_url}/internal/v1/tasks/enqueue",
        #     json=payload,
        # )
        # response.raise_for_status()
        # return response.json()

        return {
            "task_id": payload["task_id"],
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "queue_position": 0,
        }

    async def get_queue_depth(self, task_type: Optional[str] = None) -> int:
        """
        Get current queue depth.

        Args:
            task_type: Optional filter by task type.

        Returns:
            Number of tasks in queue.
        """
        # MVP: Return mock value
        return 0

    async def estimate_completion_time(
        self,
        task_count: int,
        priority: Priority,
    ) -> int:
        """
        Estimate completion time in seconds.

        Based on queue depth and historical task duration.

        Args:
            task_count: Number of tasks to complete.
            priority: Job priority level.

        Returns:
            Estimated seconds to completion.
        """
        # MVP: Simple linear estimate
        # In production, would use historical p50 duration data
        base_time_per_task = 30  # seconds

        # Adjust for priority
        priority_multiplier = {
            Priority.CRITICAL: 0.5,
            Priority.HIGH: 0.75,
            Priority.MEDIUM: 1.0,
            Priority.LOW: 1.5,
        }.get(priority, 1.0)

        queue_depth = await self.get_queue_depth()
        queue_wait = queue_depth * 5  # 5s per queued task

        return int((task_count * base_time_per_task * priority_multiplier) + queue_wait)
