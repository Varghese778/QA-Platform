"""TaskQueueManager - Redis-backed priority queues per agent type."""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import redis.asyncio as redis

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import (
    TaskType,
    TaskStatus,
    Priority,
    TaskQueueEntry,
    PRIORITY_SCORES,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key patterns
QUEUE_KEY_PREFIX = "task_queue:"
TASK_DATA_KEY_PREFIX = "task_data:"
TASK_STATUS_KEY_PREFIX = "task_status:"


class QueueFullError(Exception):
    """Raised when queue capacity is exceeded."""

    def __init__(self, task_type: TaskType, depth: int):
        self.task_type = task_type
        self.depth = depth
        super().__init__(f"Queue for {task_type.value} is full ({depth} tasks)")


class DuplicateTaskError(Exception):
    """Raised when a duplicate task_id is submitted."""

    def __init__(self, task_id: UUID):
        self.task_id = task_id
        super().__init__(f"Task {task_id} already exists")


# Global Redis connection
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class TaskQueueManager:
    """
    Manages per-agent-type priority queues using Redis sorted sets.

    Each task type has its own sorted set where:
    - Score = priority_score + (timestamp in milliseconds / 10^13)
    - This ensures priority ordering with FIFO within same priority
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client

    async def get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    def _get_queue_key(self, task_type: TaskType) -> str:
        """Get Redis key for a task type's queue."""
        return f"{QUEUE_KEY_PREFIX}{task_type.value}"

    def _get_task_data_key(self, task_id: UUID) -> str:
        """Get Redis key for task data."""
        return f"{TASK_DATA_KEY_PREFIX}{task_id}"

    def _get_task_status_key(self, task_id: UUID) -> str:
        """Get Redis key for task status."""
        return f"{TASK_STATUS_KEY_PREFIX}{task_id}"

    def _compute_priority_score(self, priority: Priority, enqueued_at: datetime) -> float:
        """
        Compute priority score for sorted set.

        Lower score = higher priority.
        Score = base_priority + (timestamp_fraction)
        """
        base_score = PRIORITY_SCORES.get(priority, 2000)
        # Add fractional timestamp to maintain FIFO within priority
        timestamp_fraction = enqueued_at.timestamp() / 10**13
        return base_score + timestamp_fraction

    async def enqueue(
        self,
        task_id: UUID,
        task_type: TaskType,
        job_id: UUID,
        project_id: UUID,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        priority: Priority,
        timeout_seconds: int,
        retry_attempt: int = 0,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> TaskQueueEntry:
        """
        Add a task to the appropriate queue.

        Returns:
            TaskQueueEntry with queue metadata.

        Raises:
            DuplicateTaskError: If task_id already exists.
            QueueFullError: If queue is at capacity.
        """
        redis_client = await self.get_redis()

        # Check for duplicate
        existing = await redis_client.exists(self._get_task_data_key(task_id))
        if existing:
            raise DuplicateTaskError(task_id)

        # Check queue depth
        queue_key = self._get_queue_key(task_type)
        depth = await redis_client.zcard(queue_key)
        if depth >= settings.max_queue_depth_per_type:
            raise QueueFullError(task_type, depth)

        # Create queue entry
        now = datetime.now(timezone.utc)
        priority_score = self._compute_priority_score(priority, now)

        entry = TaskQueueEntry(
            queue_id=uuid4(),
            task_id=task_id,
            task_type=task_type,
            job_id=job_id,
            project_id=project_id,
            payload=payload,
            context=context,
            priority=priority,
            priority_score=int(priority_score * 10**6),  # Store as int
            timeout_seconds=timeout_seconds,
            retry_attempt=retry_attempt,
            model_config_data=model_config,
            enqueued_at=now,
            status=TaskStatus.WAITING,
        )

        # Store task data
        task_data = entry.model_dump(mode="json")
        await redis_client.setex(
            self._get_task_data_key(task_id),
            settings.queue_entry_ttl_seconds,
            json.dumps(task_data),
        )

        # Store status separately for quick access
        await redis_client.setex(
            self._get_task_status_key(task_id),
            settings.queue_entry_ttl_seconds,
            TaskStatus.WAITING.value,
        )

        # Add to sorted set queue
        await redis_client.zadd(queue_key, {str(task_id): priority_score})

        logger.info(
            f"Enqueued task {task_id} to {task_type.value} queue "
            f"(priority={priority.value}, score={priority_score:.6f})"
        )

        return entry

    async def dequeue(self, task_type: TaskType) -> Optional[TaskQueueEntry]:
        """
        Remove and return the highest-priority task from a queue.

        Returns:
            TaskQueueEntry or None if queue is empty.
        """
        redis_client = await self.get_redis()
        queue_key = self._get_queue_key(task_type)

        # Get highest priority task (lowest score)
        results = await redis_client.zrange(queue_key, 0, 0)
        if not results:
            return None

        task_id_str = results[0]

        # Remove from queue
        removed = await redis_client.zrem(queue_key, task_id_str)
        if not removed:
            return None  # Already removed by another worker

        # Get task data
        task_data_json = await redis_client.get(
            self._get_task_data_key(UUID(task_id_str))
        )
        if not task_data_json:
            logger.warning(f"Task data not found for {task_id_str}")
            return None

        entry = TaskQueueEntry.model_validate_json(task_data_json)
        entry.dequeued_at = datetime.now(timezone.utc)
        entry.status = TaskStatus.PROCESSING

        # Update status
        await redis_client.setex(
            self._get_task_status_key(entry.task_id),
            settings.queue_entry_ttl_seconds,
            TaskStatus.PROCESSING.value,
        )

        # Update stored task data
        await redis_client.setex(
            self._get_task_data_key(entry.task_id),
            settings.queue_entry_ttl_seconds,
            entry.model_dump_json(),
        )

        logger.info(f"Dequeued task {entry.task_id} from {task_type.value} queue")

        return entry

    async def get_task(self, task_id: UUID) -> Optional[TaskQueueEntry]:
        """Get task data by ID."""
        redis_client = await self.get_redis()

        task_data_json = await redis_client.get(self._get_task_data_key(task_id))
        if not task_data_json:
            return None

        return TaskQueueEntry.model_validate_json(task_data_json)

    async def get_task_status(self, task_id: UUID) -> Optional[TaskStatus]:
        """Get task status by ID."""
        redis_client = await self.get_redis()

        status_str = await redis_client.get(self._get_task_status_key(task_id))
        if not status_str:
            return None

        return TaskStatus(status_str)

    async def update_task_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update task status."""
        redis_client = await self.get_redis()

        await redis_client.setex(
            self._get_task_status_key(task_id),
            settings.queue_entry_ttl_seconds,
            status.value,
        )

        # Update full task data if exists
        task_data_json = await redis_client.get(self._get_task_data_key(task_id))
        if task_data_json:
            entry = TaskQueueEntry.model_validate_json(task_data_json)
            entry.status = status
            await redis_client.setex(
                self._get_task_data_key(task_id),
                settings.queue_entry_ttl_seconds,
                entry.model_dump_json(),
            )

    async def get_queue_depth(self, task_type: TaskType) -> int:
        """Get number of tasks in a queue."""
        redis_client = await self.get_redis()
        return await redis_client.zcard(self._get_queue_key(task_type))

    async def get_oldest_queued_at(self, task_type: TaskType) -> Optional[datetime]:
        """Get timestamp of oldest task in queue."""
        redis_client = await self.get_redis()
        queue_key = self._get_queue_key(task_type)

        results = await redis_client.zrange(queue_key, 0, 0)
        if not results:
            return None

        task_id_str = results[0]
        task_data_json = await redis_client.get(
            self._get_task_data_key(UUID(task_id_str))
        )
        if not task_data_json:
            return None

        entry = TaskQueueEntry.model_validate_json(task_data_json)
        return entry.enqueued_at

    async def get_all_queue_depths(self) -> Dict[TaskType, int]:
        """Get depth of all queues."""
        depths = {}
        for task_type in TaskType:
            depths[task_type] = await self.get_queue_depth(task_type)
        return depths

    async def requeue(self, entry: TaskQueueEntry) -> None:
        """Re-add a task to the queue (for retries)."""
        redis_client = await self.get_redis()
        queue_key = self._get_queue_key(entry.task_type)

        # Update entry
        entry.status = TaskStatus.WAITING
        entry.dequeued_at = None

        # Recompute priority score (maintains original enqueue time)
        priority_score = self._compute_priority_score(entry.priority, entry.enqueued_at)

        # Add back to queue
        await redis_client.zadd(queue_key, {str(entry.task_id): priority_score})

        # Update stored data
        await redis_client.setex(
            self._get_task_data_key(entry.task_id),
            settings.queue_entry_ttl_seconds,
            entry.model_dump_json(),
        )
        await redis_client.setex(
            self._get_task_status_key(entry.task_id),
            settings.queue_entry_ttl_seconds,
            TaskStatus.WAITING.value,
        )

        logger.info(f"Re-queued task {entry.task_id} for retry")
