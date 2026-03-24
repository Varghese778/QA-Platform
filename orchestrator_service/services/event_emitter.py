"""EventEmitter - Publishes state change events to Async Processing."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from orchestrator_service.config import get_settings
from orchestrator_service.models import Job, Task, EventType

logger = logging.getLogger(__name__)
settings = get_settings()


class EventEmitter:
    """
    Publishes state change events to the Async Processing layer.

    Events are used for real-time notifications and audit trails.
    """

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
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

    async def emit_job_event(
        self,
        job: Job,
        event_type: EventType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a job-level state change event.

        Args:
            job: The job that changed state.
            event_type: Type of event.
            metadata: Additional event metadata.
        """
        event = {
            "job_id": str(job.job_id),
            "project_id": str(job.project_id),
            "event_type": event_type.value,
            "stage": "JOB",
            "status": job.status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "caller_id": str(job.caller_id),
                "priority": job.priority.value,
                "environment_target": job.environment_target.value,
                **(metadata or {}),
            },
        }

        if job.error_reason:
            event["metadata"]["error_reason"] = job.error_reason

        await self._publish_event(event)

    async def emit_task_event(
        self,
        task: Task,
        job: Job,
        event_type: EventType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a task-level state change event.

        Args:
            task: The task that changed state.
            job: The parent job.
            event_type: Type of event.
            metadata: Additional event metadata.
        """
        event = {
            "job_id": str(job.job_id),
            "project_id": str(job.project_id),
            "event_type": event_type.value,
            "stage": task.task_type.value,
            "task_id": str(task.task_id),
            "status": task.status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                **(metadata or {}),
            },
        }

        if task.assigned_agent_id:
            event["metadata"]["agent_id"] = str(task.assigned_agent_id)
        if task.error_message:
            event["metadata"]["error_message"] = task.error_message

        await self._publish_event(event)

    async def _publish_event(self, event: Dict[str, Any]) -> None:
        """
        Publish event to Async Processing service.

        For MVP, this mocks the publish operation.
        """
        # MVP: Log event instead of publishing
        logger.info(
            f"[EVENT] {event['event_type']} for job {event['job_id']}, "
            f"stage: {event['stage']}"
        )

        # In production, uncomment:
        # try:
        #     client = await self.get_http_client()
        #     response = await client.post(
        #         f"{settings.async_processing_url}/internal/v1/events",
        #         json=event,
        #     )
        #     response.raise_for_status()
        # except Exception as e:
        #     logger.error(f"Failed to publish event: {e}")
        #     # Store in outbox for retry
        #     await self._store_in_outbox(event)

    async def _store_in_outbox(self, event: Dict[str, Any]) -> None:
        """Store failed event in outbox for later retry."""
        # MVP: Just log the failure
        logger.warning(f"Event stored in outbox for retry: {event['event_type']}")

    # Convenience methods for common events
    async def emit_job_queued(self, job: Job) -> None:
        """Emit JOB_QUEUED event."""
        await self.emit_job_event(job, EventType.JOB_QUEUED)

    async def emit_job_processing(self, job: Job) -> None:
        """Emit JOB_PROCESSING event."""
        await self.emit_job_event(job, EventType.JOB_PROCESSING)

    async def emit_job_awaiting_execution(self, job: Job) -> None:
        """Emit JOB_AWAITING_EXECUTION event."""
        await self.emit_job_event(job, EventType.JOB_AWAITING_EXECUTION)

    async def emit_job_complete(self, job: Job, metadata: Optional[Dict] = None) -> None:
        """Emit JOB_COMPLETE event."""
        await self.emit_job_event(job, EventType.JOB_COMPLETE, metadata)

    async def emit_job_failed(self, job: Job) -> None:
        """Emit JOB_FAILED event."""
        await self.emit_job_event(job, EventType.JOB_FAILED)

    async def emit_job_cancelled(self, job: Job) -> None:
        """Emit JOB_CANCELLED event."""
        await self.emit_job_event(job, EventType.JOB_CANCELLED)

    async def emit_task_queued(self, task: Task, job: Job) -> None:
        """Emit TASK_QUEUED event."""
        await self.emit_task_event(task, job, EventType.TASK_QUEUED)

    async def emit_task_running(self, task: Task, job: Job) -> None:
        """Emit TASK_RUNNING event."""
        await self.emit_task_event(task, job, EventType.TASK_RUNNING)

    async def emit_task_complete(self, task: Task, job: Job) -> None:
        """Emit TASK_COMPLETE event."""
        await self.emit_task_event(task, job, EventType.TASK_COMPLETE)

    async def emit_task_failed(self, task: Task, job: Job) -> None:
        """Emit TASK_FAILED event."""
        await self.emit_task_event(task, job, EventType.TASK_FAILED)

    async def emit_task_retrying(self, task: Task, job: Job) -> None:
        """Emit TASK_RETRYING event."""
        await self.emit_task_event(task, job, EventType.TASK_RETRYING)
