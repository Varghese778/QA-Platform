"""Execution Request Handler - accepts and queues execution requests."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from execution_engine.config import get_settings
from execution_engine.models import ExecutionRecord
from execution_engine.schemas.enums import ExecutionStatus, TestEnvironment

logger = logging.getLogger(__name__)
settings = get_settings()


class ExecutionRequestHandler:
    """Handles execution requests and queuing."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.redis = await redis.from_url(settings.redis_url)
        logger.info("ExecutionRequestHandler connected to Redis")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def accept_request(
        self,
        project_id: UUID,
        job_id: UUID,
        test_suite_id: UUID,
        test_cases: list,
        environment: TestEnvironment = TestEnvironment.UNIT,
        timeout_seconds: Optional[int] = None,
        variables: Optional[dict] = None,
        tags: Optional[list] = None,
    ) -> UUID:
        """
        Accept an execution request and queue it.

        Args:
            project_id: Project ID
            job_id: Job ID from orchestrator
            test_suite_id: Test suite ID
            test_cases: List of test case definitions
            environment: Test environment type
            timeout_seconds: Execution timeout
            variables: Environment variables
            tags: Tags for execution

        Returns:
            Execution ID
        """
        execution_id = uuid4()

        # Create execution record
        execution = ExecutionRecord(
            execution_id=execution_id,
            project_id=project_id,
            job_id=job_id,
            test_suite_id=test_suite_id,
            status=ExecutionStatus.PENDING,
            environment=environment,
            total_tests=len(test_cases),
        )

        self.db.add(execution)
        await self.db.flush()

        logger.info(
            f"Created execution {execution_id} in project {project_id} "
            f"with {len(test_cases)} tests"
        )

        # Queue the execution
        if self.redis:
            execution_request = {
                "execution_id": str(execution_id),
                "project_id": str(project_id),
                "job_id": str(job_id),
                "test_suite_id": str(test_suite_id),
                "test_cases": test_cases,
                "environment": environment.value,
                "timeout_seconds": timeout_seconds,
                "variables": variables or {},
                "tags": tags or [],
            }

            await self.redis.rpush(
                settings.execution_queue_name,
                json.dumps(execution_request),
            )

            logger.info(f"Queued execution {execution_id}")

        return execution_id

    async def get_execution(
        self, execution_id: UUID, project_id: UUID
    ) -> Optional[ExecutionRecord]:
        """Get an execution record."""
        stmt = select(ExecutionRecord).where(
            ExecutionRecord.execution_id == execution_id,
            ExecutionRecord.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def cancel_execution(
        self, execution_id: UUID, project_id: UUID, reason: Optional[str] = None
    ) -> bool:
        """
        Cancel an execution.

        Returns:
            True if cancelled, False if not found or already completed
        """
        execution = await self.get_execution(execution_id, project_id)

        if not execution:
            return False

        # Only cancel if not yet completed
        if execution.status in [
            ExecutionStatus.PASSED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ERROR,
            ExecutionStatus.CANCELLED,
        ]:
            return False

        execution.status = ExecutionStatus.CANCELLED
        execution.cancelled_at = datetime.now(timezone.utc)
        if reason:
            execution.error_message = f"Cancelled: {reason}"

        await self.db.flush()

        logger.info(f"Cancelled execution {execution_id}")
        return True

    async def dequeue_execution(self) -> Optional[dict]:
        """
        Dequeue an execution request from Redis.

        Returns:
            Execution request dict or None if queue is empty
        """
        if not self.redis:
            return None

        result = await self.redis.blpop(settings.execution_queue_name, timeout=1)

        if not result:
            return None

        _, request_json = result
        request = json.loads(request_json)

        # Update status to RUNNING
        execution_id = UUID(request["execution_id"])
        stmt = select(ExecutionRecord).where(
            ExecutionRecord.execution_id == execution_id,
        )
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()

        if execution:
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.now(timezone.utc)
            await self.db.flush()

        return request
