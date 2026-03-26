"""API routes for Observability & Logging."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from observability.config import get_settings
from observability.database import get_db
from observability.models import LogEntry as LogEntryModel, MetricSample as MetricSampleModel, TraceSpan as TraceSpanModel, AlertEvent as AlertEventModel
from observability.schemas.enums import LogLevel, MetricType, SpanStatus, ComparisonOperator, AlertSeverity
from observability.schemas.tasks import (
    LogRequest, LogResponse, LogQuery,
    MetricWriteRequest, MetricResponse,
    TraceSpanRequest, Trace,
    CreateAlertRuleRequest, AlertEvent, AlertRule, AlertResponse,
    HealthResponse,
)
from observability.services.log_services import LogCollector, LogQueryEngine
from observability.services.metrics_services import MetricsReceiver, MetricsQueryEngine
from observability.services.trace_services import TraceCollector, TraceQueryEngine
from observability.services.alert_engine import AlertEngine

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/internal/v1", tags=["observability"])


# =====================================================================
# Log Endpoints
# =====================================================================


@router.post("/logs", status_code=status.HTTP_201_CREATED)
async def write_log(
    request: LogRequest,
    db: AsyncSession = Depends(get_db),
):
    """Write a log entry."""
    try:
        collector = LogCollector(db)
        log_id = await collector.write_log(
            project_id=request.project_id,
            service=request.service,
            level=request.level,
            message=request.message,
            trace_id=request.trace_id,
            context=request.context,
        )
        await db.commit()
        return {"log_id": str(log_id), "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"Failed to write log: {e}")
        raise HTTPException(status_code=500, detail="Failed to write log")


@router.post("/logs/query", response_model=LogResponse)
async def query_logs(
    request: LogQuery,
    db: AsyncSession = Depends(get_db),
):
    """Query logs with filters."""
    try:
        engine = LogQueryEngine(db)
        result = await engine.query(
            project_id=request.project_id,
            service=request.service,
            level=request.level,
            start_time=request.start_time,
            end_time=request.end_time,
            search_text=request.search_text,
            limit=request.limit,
            offset=request.offset,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to query logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to query logs")


# =====================================================================
# Metrics Endpoints
# =====================================================================


@router.post("/metrics/write", status_code=status.HTTP_201_CREATED)
async def write_metric(
    request: MetricWriteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Write a metric value."""
    try:
        receiver = MetricsReceiver(db)
        metric_id = await receiver.write_metric(
            project_id=request.project_id,
            service=request.service,
            metric_name=request.metric_name,
            metric_type=request.metric_type,
            value=request.value,
            labels=request.labels,
        )
        await db.commit()
        return {"metric_id": str(metric_id), "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"Failed to write metric: {e}")
        raise HTTPException(status_code=500, detail="Failed to write metric")


@router.post("/metrics/query")
async def query_metrics(
    project_id: UUID = Query(...),
    service: str = Query(...),
    metric_name: str = Query(...),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Query metrics for a time range."""
    try:
        engine = MetricsQueryEngine(db)
        result = await engine.query(
            project_id=project_id,
            service=service,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to query metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to query metrics")


@router.post("/metrics/query_range")
async def query_metrics_range(
    project_id: UUID = Query(...),
    service: str = Query(...),
    metric_name: str = Query(...),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    step_seconds: int = Query(60, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Query metrics with aggregation."""
    try:
        engine = MetricsQueryEngine(db)
        result = await engine.query_range(
            project_id=project_id,
            service=service,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            step_seconds=step_seconds,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to query metrics range: {e}")
        raise HTTPException(status_code=500, detail="Failed to query metrics range")


# =====================================================================
# Trace Endpoints
# =====================================================================


@router.post("/traces", status_code=status.HTTP_201_CREATED)
async def write_trace_span(
    request: TraceSpanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Write a trace span."""
    try:
        collector = TraceCollector(db)
        span_id = await collector.write_span(
            project_id=request.project_id,
            trace_id=request.trace_id,
            service=request.service,
            operation_name=request.operation_name,
            status=request.status,
            start_time=request.start_time,
            end_time=request.end_time,
            parent_span_id=request.parent_span_id,
            tags=request.tags,
            logs=request.logs,
        )
        await db.commit()
        return {"span_id": str(span_id), "trace_id": str(request.trace_id)}
    except Exception as e:
        logger.error(f"Failed to write trace: {e}")
        raise HTTPException(status_code=500, detail="Failed to write trace")


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get a trace by ID."""
    try:
        engine = TraceQueryEngine(db)
        trace = await engine.get_trace(project_id, trace_id)

        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        return trace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trace: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trace")


@router.post("/traces/search")
async def search_traces(
    project_id: UUID = Query(...),
    service: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    min_duration_ms: Optional[float] = Query(None),
    max_duration_ms: Optional[float] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Search traces."""
    try:
        engine = TraceQueryEngine(db)
        traces = await engine.search(
            project_id=project_id,
            service=service,
            operation=operation,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return {"traces": traces, "total_count": len(traces)}
    except Exception as e:
        logger.error(f"Failed to search traces: {e}")
        raise HTTPException(status_code=500, detail="Failed to search traces")


# =====================================================================
# Alert Endpoints
# =====================================================================


@router.post("/alerts/rules", status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    request: CreateAlertRuleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create an alert rule."""
    try:
        engine = AlertEngine(db)
        rule_id = await engine.create_rule(
            project_id=request.project_id,
            name=request.name,
            description=request.description,
            metric_name=request.metric_name,
            service=request.service,
            operator=request.operator,
            threshold=request.threshold,
            severity=request.severity,
            duration_seconds=request.duration_seconds,
        )
        await db.commit()
        return {"rule_id": str(rule_id), "created_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"Failed to create alert rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to create alert rule")


@router.get("/alerts/rules")
async def list_alert_rules(
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """List alert rules for a project."""
    try:
        engine = AlertEngine(db)
        rules = await engine.get_rules(project_id)
        return {"rules": rules, "total_count": len(rules)}
    except Exception as e:
        logger.error(f"Failed to list alert rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to list alert rules")


@router.get("/alerts/active", response_model=AlertResponse)
async def get_active_alerts(
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get active alerts for a project."""
    try:
        engine = AlertEngine(db)
        alerts = await engine.get_active_alerts(project_id)
        return AlertResponse(alerts=alerts, total_count=len(alerts))
    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active alerts")


@router.post("/alerts/{alert_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_alert(
    alert_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Resolve an alert."""
    try:
        engine = AlertEngine(db)
        success = await engine.resolve_alert(alert_id, project_id)

        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")

        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


# =====================================================================
# Health Check
# =====================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    try:
        from observability import __version__

        # Count entries
        log_stmt = select(func.count()).select_from(LogEntryModel)
        log_result = await db.execute(log_stmt)
        log_count = log_result.scalar() or 0

        metric_stmt = select(func.count()).select_from(MetricSampleModel)
        metric_result = await db.execute(metric_stmt)
        metric_count = metric_result.scalar() or 0

        trace_stmt = select(func.count()).select_from(TraceSpanModel)
        trace_result = await db.execute(trace_stmt)
        trace_count = trace_result.scalar() or 0

        alert_stmt = select(func.count()).select_from(AlertEventModel).where(AlertEventModel.status == "ACTIVE")
        alert_result = await db.execute(alert_stmt)
        alert_count = alert_result.scalar() or 0

        return HealthResponse(
            status="ok",
            version=__version__,
            log_count=log_count,
            metric_count=metric_count,
            trace_count=trace_count,
            active_alerts=alert_count,
            database_latency_ms=0,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")
