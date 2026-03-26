"""Schemas package - exports all Pydantic schemas."""

from observability.schemas.enums import (
    LogLevel,
    MetricType,
    SpanStatus,
    AlertSeverity,
    AlertStatus,
    ComparisonOperator,
)
from observability.schemas.tasks import (
    LogEntry,
    LogRequest,
    LogQuery,
    LogResponse,
    MetricSample,
    MetricWriteRequest,
    MetricQuery,
    MetricQueryRangeRequest,
    MetricResponse,
    MetricsResponse,
    TraceSpan,
    TraceSpanRequest,
    Trace,
    TraceQuery,
    TraceQueryResponse,
    AlertRule,
    CreateAlertRuleRequest,
    AlertEvent,
    AlertResponse,
    HealthResponse,
    ErrorDetail,
)

__all__ = [
    # Enums
    "LogLevel",
    "MetricType",
    "SpanStatus",
    "AlertSeverity",
    "AlertStatus",
    "ComparisonOperator",
    # Log schemas
    "LogEntry",
    "LogRequest",
    "LogQuery",
    "LogResponse",
    # Metric schemas
    "MetricSample",
    "MetricWriteRequest",
    "MetricQuery",
    "MetricQueryRangeRequest",
    "MetricResponse",
    "MetricsResponse",
    # Trace schemas
    "TraceSpan",
    "TraceSpanRequest",
    "Trace",
    "TraceQuery",
    "TraceQueryResponse",
    # Alert schemas
    "AlertRule",
    "CreateAlertRuleRequest",
    "AlertEvent",
    "AlertResponse",
    # Response schemas
    "HealthResponse",
    "ErrorDetail",
]
