"""Runner Provisioner and Test Runner - provision and execute tests."""

import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from execution_engine.config import get_settings
from execution_engine.models import RunnerInstance, TestResult
from execution_engine.schemas.enums import TestResultStatus

logger = logging.getLogger(__name__)
settings = get_settings()


class RunnerProvisioner:
    """Provisions test runner instances (mock Docker)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def provision_runner(self) -> UUID:
        """
        Provision a new test runner instance.

        In production, would create Docker container.
        For MVP, mock provisioning and return runner ID.

        Returns:
            Runner instance ID
        """
        runner_id = uuid4()

        # Mock: create runner instance record
        runner = RunnerInstance(
            runner_id=runner_id,
            container_id=f"mock_container_{str(runner_id)[:8]}",
            status="IDLE",
        )

        self.db.add(runner)
        await self.db.flush()

        logger.info(f"Provisioned runner {runner_id}")

        # Mock: simulate startup delay
        await asyncio.sleep(0.5)

        return runner_id

    async def decommission_runner(self, runner_id: UUID) -> bool:
        """Decommission a runner instance."""
        stmt = select(RunnerInstance).where(RunnerInstance.runner_id == runner_id)
        result = await self.db.execute(stmt)
        runner = result.scalar_one_or_none()

        if not runner:
            return False

        runner.status = "OFFLINE"
        runner.decommissioned_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"Decommissioned runner {runner_id}")
        return True

    async def get_available_runner(self) -> Optional[UUID]:
        """Get an available idle runner."""
        stmt = select(RunnerInstance).where(
            RunnerInstance.status == "IDLE",
            RunnerInstance.decommissioned_at == None,
        )
        result = await self.db.execute(stmt)
        runner = result.scalar_one_or_none()

        if runner:
            return runner.runner_id
        return None

    async def mark_runner_busy(self, runner_id: UUID, execution_id: UUID) -> bool:
        """Mark a runner as busy with an execution."""
        stmt = select(RunnerInstance).where(RunnerInstance.runner_id == runner_id)
        result = await self.db.execute(stmt)
        runner = result.scalar_one_or_none()

        if not runner:
            return False

        runner.status = "BUSY"
        runner.active_execution_id = execution_id
        await self.db.flush()
        return True

    async def mark_runner_idle(self, runner_id: UUID) -> bool:
        """Mark a runner as idle."""
        stmt = select(RunnerInstance).where(RunnerInstance.runner_id == runner_id)
        result = await self.db.execute(stmt)
        runner = result.scalar_one_or_none()

        if not runner:
            return False

        runner.status = "IDLE"
        runner.active_execution_id = None
        await self.db.flush()
        return True


class TestRunner:
    """Executes tests in a runner instance."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_test_case(
        self,
        execution_id: UUID,
        project_id: UUID,
        test_name: str,
        test_case: dict,
        runner_id: UUID,
    ) -> TestResult:
        """
        Execute a single test case.

        In production, would communicate with runner via Docker.
        For MVP, simulate execution with random results.

        Args:
            execution_id: Parent execution ID
            project_id: Project ID
            test_name: Test name
            test_case: Test case definition
            runner_id: Runner instance ID

        Returns:
            TestResult record
        """
        logger.info(f"Executing test {test_name}")

        # Mock: simulate test execution delay
        duration = random.uniform(0.5, 5.0)
        await asyncio.sleep(min(duration, settings.execution_per_test_timeout_seconds))

        # Mock: randomly assign result
        result_rand = random.random()
        if result_rand < 0.7:  # 70% pass rate
            status = TestResultStatus.PASS
            error_message = None
        elif result_rand < 0.9:  # 20% fail rate
            status = TestResultStatus.FAIL
            error_message = f"Assertion failed: {test_name}"
        else:  # 10% error rate
            status = TestResultStatus.ERROR
            error_message = f"Test error: {test_name}"

        # Create test result record
        result = TestResult(
            result_id=uuid4(),
            execution_id=execution_id,
            project_id=project_id,
            test_name=test_name,
            test_case_id=test_case.get("test_id"),
            status=status,
            duration_seconds=duration,
            error_message=error_message,
            output=f"Test {test_name} executed",
            is_flaky=False,
            retry_count=0,
        )

        self.db.add(result)
        await self.db.flush()

        logger.info(f"Test {test_name} completed with status {status.value}")
        return result

    async def execute_test_cases(
        self,
        execution_id: UUID,
        project_id: UUID,
        test_cases: List[dict],
        runner_id: UUID,
    ) -> List[TestResult]:
        """Execute multiple test cases sequentially."""
        results = []

        for test_case in test_cases:
            test_name = test_case.get("name", "Unknown Test")
            result = await self.execute_test_case(
                execution_id, project_id, test_name, test_case, runner_id
            )
            results.append(result)

        logger.info(f"Executed {len(results)} test cases")
        return results
