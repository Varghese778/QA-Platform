"""API routes for Execution Engine."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from execution_engine.config import get_settings
from execution_engine.database import get_db
from execution_engine.models import ExecutionRecord, TestResult, ExecutionReport
from execution_engine.schemas.enums import ExecutionStatus, TestEnvironment
from execution_engine.schemas.tasks import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionRecord as ExecutionRecordSchema,
    ExecutionReport as ExecutionReportSchema,
    ExecutionListResponse,
    CancelExecutionRequest,
    CancelExecutionResponse,
    HealthResponse,
)
from execution_engine.services.execution_handler import ExecutionRequestHandler
from execution_engine.services.runner import RunnerProvisioner, TestRunner
from execution_engine.services.flaky_detector import FlakyDetector
from execution_engine.services.report_builder import ReportBuilder

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/internal/v1", tags=["execution-engine"])


# =====================================================================
# Execution Endpoints
# =====================================================================


@router.post("/executions", response_model=ExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_execution(
    request: ExecutionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger test execution."""
    try:
        # Validate request
        if not request.test_cases:
            raise ValueError("At least one test case required")

        # Accept execution request
        handler = ExecutionRequestHandler(db)
        await handler.connect()

        execution_id = await handler.accept_request(
            project_id=request.project_id,
            job_id=request.job_id,
            test_suite_id=request.test_suite_id,
            test_cases=request.test_cases,
            environment=request.environment,
            timeout_seconds=request.timeout_seconds,
            variables=request.variables,
            tags=request.tags,
        )

        await handler.disconnect()
        await db.commit()

        return ExecutionResponse(
            execution_id=execution_id,
            status=ExecutionStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to trigger execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger execution",
        )


@router.get("/executions/{execution_id}", response_model=ExecutionRecordSchema)
async def get_execution_status(
    execution_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get execution status and metrics."""
    try:
        stmt = select(ExecutionRecord).where(
            and_(
                ExecutionRecord.execution_id == execution_id,
                ExecutionRecord.project_id == project_id,
            )
        )
        result = await db.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found",
            )

        return ExecutionRecordSchema(
            execution_id=execution.execution_id,
            project_id=execution.project_id,
            job_id=execution.job_id,
            test_suite_id=execution.test_suite_id,
            status=execution.status,
            environment=execution.environment,
            total_tests=execution.total_tests,
            passed_tests=execution.passed_tests,
            failed_tests=execution.failed_tests,
            error_tests=execution.error_tests,
            skipped_tests=execution.skipped_tests,
            flaky_tests=execution.flaky_tests,
            total_duration_seconds=execution.total_duration_seconds,
            coverage_percentage=execution.coverage_percentage,
            error_message=execution.error_message,
            created_at=execution.created_at,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            cancelled_at=execution.cancelled_at,
            version=execution.version,
        )

    except Exception as e:
        logger.error(f"Failed to get execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution",
        )


@router.post("/executions/{execution_id}/cancel", response_model=CancelExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    project_id: UUID = Query(...),
    request: CancelExecutionRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running execution."""
    try:
        handler = ExecutionRequestHandler(db)
        reason = request.reason if request else None

        cancelled = await handler.cancel_execution(execution_id, project_id, reason)

        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution cannot be cancelled",
            )

        # Get updated execution
        stmt = select(ExecutionRecord).where(
            ExecutionRecord.execution_id == execution_id,
            ExecutionRecord.project_id == project_id,
        )
        result = await db.execute(stmt)
        execution = result.scalar_one()

        await db.commit()

        return CancelExecutionResponse(
            execution_id=execution_id,
            status=execution.status,
            cancelled_at=execution.cancelled_at,
        )

    except Exception as e:
        logger.error(f"Failed to cancel execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel execution",
        )


# =====================================================================
# Report & Results Endpoints
# =====================================================================


@router.get("/executions/{execution_id}/report", response_model=ExecutionReportSchema)
async def get_execution_report(
    execution_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed execution report."""
    try:
        builder = ReportBuilder(db)
        report = await builder.get_report(execution_id, project_id)

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report not found for execution {execution_id}",
            )

        from execution_engine.schemas.tasks import TestCaseResult, TestStepResult

        test_results = []
        if report.test_results:
            for tr in report.test_results:
                test_results.append(
                    TestCaseResult(
                        test_name=tr.get("test_name", "Unknown"),
                        status=tr.get("status", "ERROR"),
                        duration_seconds=tr.get("duration_seconds", 0.0),
                        error_message=tr.get("error_message"),
                        is_flaky=tr.get("is_flaky", False),
                    )
                )

        return ExecutionReportSchema(
            execution_id=report.execution_id,
            status=ExecutionStatus.PASSED
            if report.failed_count == 0 and report.error_count == 0
            else ExecutionStatus.FAILED,
            summary=report.summary,
            total_tests=report.total_tests,
            passed_count=report.passed_count,
            failed_count=report.failed_count,
            error_count=report.error_count,
            flaky_count=report.flaky_count,
            total_duration_seconds=report.total_duration_seconds,
            coverage_percentage=report.coverage_percentage,
            test_results=test_results,
            created_at=report.created_at,
        )

    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get report",
        )


# =====================================================================
# Health Check
# =====================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    try:
        from execution_engine import __version__

        # Count active executions
        stmt = select(ExecutionRecord).where(
            ExecutionRecord.status.in_(
                [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]
            )
        )
        result = await db.execute(stmt)
        active_count = len(result.scalars().all())

        # Count available runners
        from execution_engine.models import RunnerInstance

        stmt = select(RunnerInstance).where(RunnerInstance.status == "IDLE")
        result = await db.execute(stmt)
        runner_count = len(result.scalars().all())

        return HealthResponse(
            status="ok",
            version=__version__,
            active_executions=active_count,
            available_runners=runner_count,
            queue_depth=0,  # Would fetch from Redis in production
            database_latency_ms=0,
            redis_latency_ms=0,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed",
        )
