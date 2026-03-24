"""Flaky Test Detector - identifies and retries flaky tests."""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from execution_engine.models import TestResult
from execution_engine.schemas.enums import TestResultStatus
from execution_engine.services.runner import TestRunner

logger = logging.getLogger(__name__)


class FlakyDetector:
    """Detects and handles flaky tests."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.runner = TestRunner(db)

    async def detect_and_retry_flaky_tests(
        self,
        execution_id: UUID,
        project_id: UUID,
        test_cases: List[dict],
        runner_id: UUID,
        retry_count: int = 1,
    ) -> List[TestResult]:
        """
        Detect failed tests and retry them once.

        If a test fails and then passes on retry, mark it as FLAKY.

        Args:
            execution_id: Execution ID
            project_id: Project ID
            test_cases: Test case definitions
            runner_id: Runner instance ID
            retry_count: Number of retries per failed test

        Returns:
            Updated TestResult records
        """
        logger.info(f"Detecting flaky tests for execution {execution_id}")

        # Get failed tests from this execution
        stmt = select(TestResult).where(
            and_(
                TestResult.execution_id == execution_id,
                TestResult.status == TestResultStatus.FAIL,
            )
        )
        result = await self.db.execute(stmt)
        failed_tests = result.scalars().all()

        if not failed_tests:
            logger.info("No failed tests to retry")
            return failed_tests

        retried_tests = []

        # Retry each failed test
        for failed_test in failed_tests:
            logger.info(
                f"Retrying flaky test candidate: {failed_test.test_name}"
            )

            # Find matching test case
            test_case = next(
                (tc for tc in test_cases if tc.get("name") == failed_test.test_name),
                None,
            )

            if not test_case:
                logger.warning(f"Could not find test case for {failed_test.test_name}")
                continue

            # Retry the test
            for attempt in range(retry_count):
                logger.debug(
                    f"Retry attempt {attempt + 1}/{retry_count} for {failed_test.test_name}"
                )

                retry_result = await self.runner.execute_test_case(
                    execution_id,
                    project_id,
                    failed_test.test_name,
                    test_case,
                    runner_id,
                )

                # If passes on retry, mark as flaky
                if retry_result.status == TestResultStatus.PASS:
                    logger.info(
                        f"Test {failed_test.test_name} is FLAKY (failed then passed)"
                    )

                    # Mark original failed test as flaky
                    failed_test.is_flaky = True
                    failed_test.retry_count += 1
                    await self.db.flush()

                    # Mark retry result as flaky too
                    retry_result.is_flaky = True
                    retry_result.status = TestResultStatus.FLAKY
                    retry_result.retry_count = attempt + 1
                    await self.db.flush()

                    retried_tests.append(retry_result)
                    break
                else:
                    # Still failing, continue retrying
                    logger.debug(f"Retry still failed for {failed_test.test_name}")
                    failed_test.retry_count += 1

        logger.info(f"Found {len(retried_tests)} flaky tests")
        return retried_tests

    async def get_flaky_tests_for_execution(
        self, execution_id: UUID
    ) -> List[TestResult]:
        """Get all flaky tests in an execution."""
        stmt = select(TestResult).where(
            and_(
                TestResult.execution_id == execution_id,
                TestResult.is_flaky == True,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
