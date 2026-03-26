"""Observability database models - Logs, metrics, traces, alerts."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Enum, Index, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from observability.database import Base
from observability.schemas.enums import (
    LogLevel,
    MetricType,
    SpanStatus,
    AlertSeverity,
    AlertStatus,
    ComparisonOperator,
)


class LogEntry(Base):
    """
    Log entry storage.

    Stores structured logs from all services.
    """

    __tablename__ = "log_entries"

    # Primary key
    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Ownership & context
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    service: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Log content
    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, name="log_level_enum"),
        nullable=False,
        index=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Tracing
    trace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Additional context
    context: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<LogEntry {self.log_id} level={self.level.value}>"


class MetricSample(Base):
    """
    Metric sample storage.

    Stores timestamped metric values from services.
    """

    __tablename__ = "metric_samples"

    # Primary key
    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Ownership
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    service: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Metric identity
    metric_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    metric_type: Mapped[MetricType] = mapped_column(
        Enum(MetricType, name="metric_type_enum"),
        nullable=False,
    )

    # Value
    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Labels/tags
    labels: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Label key-value pairs for metric dimensions",
    )

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<MetricSample {self.metric_id} {self.metric_name}={self.value}>"


class TraceSpan(Base):
    """
    Distributed trace span storage.

    Stores individual spans in distributed traces.
    """

    __tablename__ = "trace_spans"

    # Primary key
    span_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Trace identity
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    parent_span_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Ownership
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    service: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Span details
    operation_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    status: Mapped[SpanStatus] = mapped_column(
        Enum(SpanStatus, name="span_status_enum"),
        nullable=False,
    )

    # Timing
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Additional data
    tags: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    logs: Mapped[Optional[List[dict]]] = mapped_column(
        ARRAY(JSON),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<TraceSpan {self.span_id} trace={self.trace_id}>"


class AlertRule(Base):
    """
    Alert rule definition.

    Stores rules for triggering alerts based on metrics.
    """

    __tablename__ = "alert_rules"

    # Primary key
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Ownership
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Rule details
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Condition
    metric_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    service: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    operator: Mapped[ComparisonOperator] = mapped_column(
        Enum(ComparisonOperator, name="comparison_operator_enum"),
        nullable=False,
    )

    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    duration_seconds: Mapped[int] = mapped_column(
        default=300,
        nullable=False,
    )

    # Properties
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity_enum"),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AlertRule {self.rule_id} name={self.name}>"


class AlertEvent(Base):
    """
    Alert event triggered by a rule.

    Stores alert instances when rules are triggered.
    """

    __tablename__ = "alert_events"

    # Primary key
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Reference
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Status
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status_enum"),
        default=AlertStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity_enum"),
        nullable=False,
    )

    # Message
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Timeline
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    silenced_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Context
    metric_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    context: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AlertEvent {self.alert_id} status={self.status.value}>"


# Composite indexes for efficient querying
__table_args__ = (
    Index(
        "ix_log_entries_project_service_timestamp",
        LogEntry.project_id,
        LogEntry.service,
        LogEntry.timestamp.desc(),
    ),
    Index(
        "ix_metric_samples_project_service_metric_timestamp",
        MetricSample.project_id,
        MetricSample.service,
        MetricSample.metric_name,
        MetricSample.timestamp.desc(),
    ),
    Index(
        "ix_trace_spans_trace_id_start_time",
        TraceSpan.trace_id,
        TraceSpan.start_time.desc(),
    ),
    Index(
        "ix_trace_spans_project_service_timestamp",
        TraceSpan.project_id,
        TraceSpan.service,
        TraceSpan.start_time.desc(),
    ),
    Index(
        "ix_alert_rules_project_enabled",
        AlertRule.project_id,
        AlertRule.enabled,
    ),
    Index(
        "ix_alert_events_project_status_triggered",
        AlertEvent.project_id,
        AlertEvent.status,
        AlertEvent.triggered_at.desc(),
    ),
)
