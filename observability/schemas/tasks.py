"""Pydantic schemas for Observability & Logging."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from observability.schemas.enums import (
    LogLevel,
    MetricType,
    SpanStatus,
    AlertSeverity,
    AlertStatus,
    ComparisonOperator,
)


# =====================================================================
# Log Schemas
# =====================================================================


class LogEntry(BaseModel):
    """Log entry."""

    log_id: UUID
    project_id: UUID
    service: str
    level: LogLevel
    message: str
    timestamp: datetime
    trace_id: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = None
    version: int


class LogRequest(BaseModel):
    """Request to write logs."""

    project_id: UUID
    service: str
    level: LogLevel
    message: str
    trace_id: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = None


class LogQuery(BaseModel):
    """Query logs with filters."""

    project_id: UUID
    service: Optional[str] = None
    level: Optional[LogLevel] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    search_text: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class LogResponse(BaseModel):
    """Response with logs."""

    logs: List[LogEntry]
    total_count: int
    limit: int
    offset: int


# =====================================================================
# Metrics Schemas
# =====================================================================


class MetricLabel(BaseModel):
    """Metric label/tag."""

    name: str
    value: str


class MetricSample(BaseModel):
    """Single metric sample."""

    metric_id: UUID
    project_id: UUID
    service: str
    metric_name: str
    metric_type: MetricType
    value: float
    labels: List[MetricLabel] = Field(default_factory=list)
    timestamp: datetime


class MetricWriteRequest(BaseModel):
    """Request to write metrics."""

    project_id: UUID
    service: str
    metric_name: str
    metric_type: MetricType
    value: float
    labels: Optional[List[Dict[str, str]]] = None


class MetricQuery(BaseModel):
    """Query metrics."""

    project_id: UUID
    service: str
    metric_name: str
    start_time: datetime
    end_time: datetime
    labels: Optional[Dict[str, str]] = None


class MetricQueryRangeRequest(BaseModel):
    """Request for range query."""

    project_id: UUID
    service: str
    metric_name: str
    start_time: datetime
    end_time: datetime
    step_seconds: int = 60
    labels: Optional[Dict[str, str]] = None


class MetricResponse(BaseModel):
    """Response with metrics."""

    metric_name: str
    values: List[tuple]  # [(timestamp, value), ...]


class MetricsResponse(BaseModel):
    """Response with multiple metric series."""

    metrics: List[MetricResponse]
    total_points: int


# =====================================================================
# Trace Schemas
# =====================================================================


class TraceSpan(BaseModel):
    """Distributed trace span."""

    span_id: UUID
    trace_id: UUID
    parent_span_id: Optional[UUID] = None
    project_id: UUID
    service: str
    operation_name: str
    status: SpanStatus
    start_time: datetime
    end_time: datetime
    duration_ms: float
    tags: Optional[Dict[str, str]] = None
    logs: Optional[List[Dict[str, Any]]] = None


class TraceSpanRequest(BaseModel):
    """Request to write trace span."""

    project_id: UUID
    trace_id: UUID
    parent_span_id: Optional[UUID] = None
    service: str
    operation_name: str
    status: SpanStatus
    start_time: datetime
    end_time: datetime
    tags: Optional[Dict[str, str]] = None
    logs: Optional[List[Dict[str, Any]]] = None


class Trace(BaseModel):
    """Complete distributed trace."""

    trace_id: UUID
    project_id: UUID
    root_service: str
    root_operation: str
    start_time: datetime
    end_time: datetime
    total_duration_ms: float
    span_count: int
    spans: List[TraceSpan]


class TraceQuery(BaseModel):
    """Query traces."""

    project_id: UUID
    service: Optional[str] = None
    operation: Optional[str] = None
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)


class TraceQueryResponse(BaseModel):
    """Response with trace summaries."""

    traces: List[Trace]
    total_count: int


# =====================================================================
# Alert Schemas
# =====================================================================


class AlertRule(BaseModel):
    """Alert rule definition."""

    rule_id: UUID
    project_id: UUID
    name: str
    description: Optional[str] = None
    metric_name: str
    service: str
    operator: ComparisonOperator
    threshold: float
    duration_seconds: int = 300  # How long condition must be true
    severity: AlertSeverity
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class CreateAlertRuleRequest(BaseModel):
    """Request to create alert rule."""

    project_id: UUID
    name: str
    description: Optional[str] = None
    metric_name: str
    service: str
    operator: ComparisonOperator
    threshold: float
    duration_seconds: int = 300
    severity: AlertSeverity


class AlertEvent(BaseModel):
    """Alert event generated by rule."""

    alert_id: UUID
    rule_id: UUID
    project_id: UUID
    status: AlertStatus
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    silenced_until: Optional[datetime] = None
    metric_value: Optional[float] = None
    context: Optional[Dict[str, Any]] = None


class AlertResponse(BaseModel):
    """Response with active alerts."""

    alerts: List[AlertEvent]
    total_count: int


# =====================================================================
# Health & Response Schemas
# =====================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    log_count: int = 0
    metric_count: int = 0
    trace_count: int = 0
    active_alerts: int = 0
    database_latency_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    """Error detail response."""

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
