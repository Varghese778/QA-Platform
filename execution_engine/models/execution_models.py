"""Execution Engine database models."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Enum, Index, String, Text, event
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from execution_engine.database import Base
from execution_engine.schemas.enums import (
    ExecutionStatus,
    TestResultStatus,
    TestEnvironment,
)


class ExecutionRecord(Base):
    """
    Central execution record.

    Tracks test suite executions with results and metrics.
    """

    __tablename__ = "execution_records"

    # Primary key
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Ownership & reference
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Project namespace",
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Orchestrator job ID",
    )

    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Status
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status_enum"),
        default=ExecutionStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Environment
    environment: Mapped[TestEnvironment] = mapped_column(
        Enum(TestEnvironment, name="test_environment_enum"),
        default=TestEnvironment.UNIT,
        nullable=False,
    )

    # Test counts
    total_tests: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    passed_tests: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    failed_tests: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    error_tests: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    skipped_tests: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    flaky_tests: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Performance
    total_duration_seconds: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False,
    )

    coverage_percentage: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False,
    )

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ExecutionRecord {self.execution_id} status={self.status.value}>"


class TestResult(Base):
    """Individual test case result."""

    __tablename__ = "test_results"

    # Primary key
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Parent execution",
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Test details
    test_name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    test_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Result
    status: Mapped[TestResultStatus] = mapped_column(
        Enum(TestResultStatus, name="test_result_status_enum"),
        nullable=False,
        index=True,
    )

    # Measurement
    duration_seconds: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    output: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Flaky detection
    is_flaky: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    retry_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Step details
    steps: Mapped[Optional[List[dict]]] = mapped_column(
        ARRAY(JSON),
        nullable=True,
        comment="Test step results",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TestResult {self.result_id} test={self.test_name}>"


class ExecutionReport(Base):
    """Aggregated execution report."""

    __tablename__ = "execution_reports"

    # Primary key
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Summary
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Aggregated metrics
    total_tests: Mapped[int] = mapped_column(nullable=False)
    passed_count: Mapped[int] = mapped_column(nullable=False)
    failed_count: Mapped[int] = mapped_column(nullable=False)
    error_count: Mapped[int] = mapped_column(nullable=False)
    flaky_count: Mapped[int] = mapped_column(default=0, nullable=False)
    total_duration_seconds: Mapped[float] = mapped_column(nullable=False)
    coverage_percentage: Mapped[float] = mapped_column(nullable=False)

    # Report data
    test_results: Mapped[Optional[List[dict]]] = mapped_column(
        ARRAY(JSON),
        nullable=True,
        comment="Detailed test results",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<ExecutionReport {self.report_id}>"


class RunnerInstance(Base):
    """Test runner instance registry."""

    __tablename__ = "runner_instances"

    # Primary key
    runner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Identification
    container_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Docker container ID",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="IDLE",
        nullable=False,
        index=True,
        comment="IDLE, BUSY, UNHEALTHY, OFFLINE",
    )

    # Activity
    active_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Heartbeat
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    decommissioned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<RunnerInstance {self.runner_id} status={self.status}>"


# Composite indexes
__table_args__ = (
    Index(
        "ix_execution_records_project_status_created",
        ExecutionRecord.project_id,
        ExecutionRecord.status,
        ExecutionRecord.created_at.desc(),
    ),
    Index(
        "ix_test_results_execution_status",
        TestResult.execution_id,
        TestResult.status,
    ),
    Index(
        "ix_runner_instances_status_heartbeat",
        RunnerInstance.status,
        RunnerInstance.last_heartbeat.desc(),
    ),
)
