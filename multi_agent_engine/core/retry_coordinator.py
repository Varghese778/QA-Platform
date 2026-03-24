"""RetryCoordinator - Determines retry eligibility and applies prompt variation."""

import asyncio
import logging
from typing import Optional

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import (
    TaskQueueEntry,
    TaskStatus,
    FailureCategory,
)
from multi_agent_engine.core.task_queue import TaskQueueManager
from multi_agent_engine.agents import AgentResult, OutputParseError

logger = logging.getLogger(__name__)
settings = get_settings()


class RetryCoordinator:
    """
    Determines retry eligibility and applies prompt variation on retry.

    Rules:
    - Max 3 retries per task
    - Exponential backoff: 10s, 30s, 90s
    - OUTPUT_PARSE_ERROR: Apply JSON repair prompt on first retry
    - LLM_API_ERROR: Retry with same prompt
    - TIMEOUT: Retry with same prompt
    """

    def __init__(self, queue_manager: TaskQueueManager):
        self.queue_manager = queue_manager
        self.backoff_seconds = settings.llm_retry_backoff_seconds

    async def should_retry(self, result: AgentResult) -> bool:
        """
        Determine if a failed task should be retried.

        Returns:
            True if task should be retried.
        """
        # Don't retry on schema mismatch
        if result.error_category == FailureCategory.SCHEMA_MISMATCH:
            return False

        # Don't retry on validation failure
        if result.error_category == FailureCategory.VALIDATION_FAILED:
            return False

        # Don't retry if budget exceeded
        if result.error_category == FailureCategory.BUDGET_EXCEEDED:
            return False

        # Get current task entry
        task_entry = await self.queue_manager.get_task(result.task_id)
        if not task_entry:
            return False

        # Check retry limit
        if task_entry.retry_attempt >= settings.max_retry_attempts:
            return False

        # Retry on: OUTPUT_PARSE_ERROR, LLM_API_ERROR, TIMEOUT, CONTEXT_TOO_LARGE
        retriable_errors = {
            FailureCategory.OUTPUT_PARSE_ERROR,
            FailureCategory.LLM_API_ERROR,
            FailureCategory.TIMEOUT,
            FailureCategory.CONTEXT_TOO_LARGE,
        }

        return result.error_category in retriable_errors

    async def retry_task(
        self,
        result: AgentResult,
        task_entry: Optional[TaskQueueEntry] = None,
    ) -> Optional[TaskQueueEntry]:
        """
        Re-queue a task for retry with optional prompt variation.

        Args:
            result: The failed task result.
            task_entry: The original task entry (fetched if not provided).

        Returns:
            Updated task entry or None if retry not possible.
        """
        if not await self.should_retry(result):
            return None

        if task_entry is None:
            task_entry = await self.queue_manager.get_task(result.task_id)
            if not task_entry:
                return None

        # Get backoff delay
        retry_attempt = task_entry.retry_attempt
        if retry_attempt < len(self.backoff_seconds):
            backoff = self.backoff_seconds[retry_attempt]
        else:
            backoff = self.backoff_seconds[-1]

        logger.info(
            f"Retrying task {result.task_id} (attempt {retry_attempt + 1}), "
            f"backoff: {backoff}s, reason: {result.error_category.value}"
        )

        # Wait for backoff
        await asyncio.sleep(backoff)

        # Increment retry counter
        task_entry.retry_attempt += 1

        # Mark for variant prompt if OUTPUT_PARSE_ERROR
        if result.error_category == FailureCategory.OUTPUT_PARSE_ERROR:
            if not task_entry.model_config_data:
                task_entry.model_config_data = {}
            task_entry.model_config_data["repair_prompt"] = True

        # Re-queue
        await self.queue_manager.requeue(task_entry)

        return task_entry

    def get_max_retries(self) -> int:
        """Get the maximum number of retry attempts."""
        return settings.max_retry_attempts

    def is_max_retries_exceeded(self, retry_attempt: int) -> bool:
        """Check if retry attempt has exceeded the maximum."""
        return retry_attempt >= settings.max_retry_attempts
