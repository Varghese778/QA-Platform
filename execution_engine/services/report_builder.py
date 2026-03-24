"""Report Builder - aggregates execution results and generates reports."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from execution_engine.config import get_settings
from execution_engine.models import ExecutionRecord, ExecutionReport, TestResult
from execution_engine.schemas.enums import ExecutionStatus, TestResultStatus

logger = logging.getLogger(__name__)
settings = get_settings()


class ReportBuilder:
    """Builds execution reports from test results."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_report(
        self, execution_id: UUID, project_id: UUID
    ) -> Optional[ExecutionReport]:
        """
        Build a comprehensive execution report.

        Aggregates test results and calculates metrics.

        Args:
            execution_id: Execution ID
            project_id: Project ID

        Returns:
            ExecutionReport or None if execution not found
        """
        logger.info(f"Building report for execution {execution_id}")

        # Get execution record
        stmt = select(ExecutionRecord).where(
            and_(
                ExecutionRecord.execution_id == execution_id,
                ExecutionRecord.project_id == project_id,
            )
        )
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            logger.warning(f"Execution {execution_id} not found")
            return None

        # Get all test results
        stmt = select(TestResult).where(TestResult.execution_id == execution_id)
        result = await self.db.execute(stmt)
        test_results = result.scalars().all()

        # Aggregate metrics
        metrics = await self._aggregate_metrics(test_results)

        # Calculate coverage
        coverage_percentage = await self._calculate_coverage(execution_id)

        # Generate summary
        summary = self._generate_summary(metrics, coverage_percentage)

        # Update execution record
        execution.passed_tests = metrics["passed"]
        execution.failed_tests = metrics["failed"]
        execution.error_tests = metrics["error"]
        execution.skipped_tests = metrics["skipped"]
        execution.flaky_tests = metrics["flaky"]
        execution.total_duration_seconds = metrics["total_duration"]
        execution.coverage_percentage = coverage_percentage

        # Determine final status
        if metrics["failed"] > 0 or metrics["error"] > 0:
            execution.status = ExecutionStatus.FAILED
        else:
            execution.status = ExecutionStatus.PASSED

        execution.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Create execution report
        report = ExecutionReport(
            report_id=uuid4(),
            execution_id=execution_id,
            project_id=project_id,
            summary=summary,
            total_tests=len(test_results),
            passed_count=metrics["passed"],
            failed_count=metrics["failed"],
            error_count=metrics["error"],
            flaky_count=metrics["flaky"],
            total_duration_seconds=metrics["total_duration"],
            coverage_percentage=coverage_percentage,
            test_results=[
                {
                    "test_name": tr.test_name,
                    "status": tr.status.value,
                    "duration_seconds": tr.duration_seconds,
                    "is_flaky": tr.is_flaky,
                    "error_message": tr.error_message,
                }
                for tr in test_results
            ],
        )

        self.db.add(report)
        await self.db.flush()

        logger.info(f"Built report {report.report_id} for execution {execution_id}")
        return report

    async def _aggregate_metrics(self, test_results: List[TestResult]) -> dict:
        """Aggregate test result metrics."""
        metrics = {
            "passed": 0,
            "failed": 0,
            "error": 0,
            "skipped": 0,
            "flaky": 0,
            "total_duration": 0.0,
        }

        for result in test_results:
            if result.status == TestResultStatus.PASS:
                metrics["passed"] += 1
            elif result.status == TestResultStatus.FAIL:
                metrics["failed"] += 1
            elif result.status == TestResultStatus.ERROR:
                metrics["error"] += 1
            elif result.status == TestResultStatus.SKIPPED:
                metrics["skipped"] += 1
            elif result.status == TestResultStatus.FLAKY:
                metrics["flaky"] += 1

            metrics["total_duration"] += result.duration_seconds

        return metrics

    async def _calculate_coverage(self, execution_id: UUID) -> float:
        """
        Calculate code coverage percentage.

        For MVP, mock implementation: return pass rate as coverage.

        Args:
            execution_id: Execution ID

        Returns:
            Coverage percentage (0-100)
        """
        stmt = select(TestResult).where(TestResult.execution_id == execution_id)
        result = await self.db.execute(stmt)
        test_results = result.scalars().all()

        if not test_results:
            return 0.0

        # Mock: calculate as pass rate * 100
        passed = sum(
            1 for tr in test_results if tr.status == TestResultStatus.PASS
        )
        coverage = (passed / len(test_results)) * 100.0

        # Cap at 100%
        return min(coverage, 100.0)

    def _generate_summary(self, metrics: dict, coverage: float) -> str:
        """Generate a text summary of the execution."""
        total = (
            metrics["passed"]
            + metrics["failed"]
            + metrics["error"]
            + metrics["skipped"]
        )

        if total == 0:
            return "No tests executed"

        pass_rate = (metrics["passed"] / total * 100) if total > 0 else 0

        summary = (
            f"Executed {total} tests: "
            f"{metrics['passed']} passed, "
            f"{metrics['failed']} failed, "
            f"{metrics['error']} errors, "
            f"{metrics['skipped']} skipped"
        )

        if metrics["flaky"] > 0:
            summary += f", {metrics['flaky']} flaky"

        summary += (
            f". Pass rate: {pass_rate:.1f}%, Coverage: {coverage:.1f}%, "
            f"Duration: {metrics['total_duration']:.1f}s"
        )

        return summary

    async def get_report(
        self, execution_id: UUID, project_id: UUID
    ) -> Optional[ExecutionReport]:
        """Get an existing report."""
        stmt = select(ExecutionReport).where(
            and_(
                ExecutionReport.execution_id == execution_id,
                ExecutionReport.project_id == project_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
