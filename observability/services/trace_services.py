"""Distributed trace collection and querying services."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from observability.models import TraceSpan as TraceSpanModel
from observability.schemas.enums import SpanStatus
from observability.schemas.tasks import TraceSpan, Trace

logger = logging.getLogger(__name__)


class TraceCollector:
    """Collects distributed trace spans."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_span(
        self,
        project_id: UUID,
        trace_id: UUID,
        service: str,
        operation_name: str,
        status: SpanStatus,
        start_time: datetime,
        end_time: datetime,
        parent_span_id: Optional[UUID] = None,
        tags: Optional[dict] = None,
        logs: Optional[List[dict]] = None,
    ) -> UUID:
        """
        Write a trace span.

        Args:
            project_id: Project ID
            trace_id: Trace ID
            service: Service name
            operation_name: Operation being traced
            status: Completion status
            start_time: Start time
            end_time: End time
            parent_span_id: Parent span ID if part of a span tree
            tags: Key-value tags
            logs: Timestamped log lines

        Returns:
            Span ID
        """
        span_id = uuid4()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        span = TraceSpanModel(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            project_id=project_id,
            service=service,
            operation_name=operation_name,
            status=status,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            tags=tags or {},
            logs=logs or [],
        )

        self.db.add(span)
        await self.db.flush()

        logger.debug(
            f"Recorded span {operation_name} in trace {trace_id}"
        )
        return span_id

    async def write_batch(
        self, spans: List[dict]
    ) -> List[UUID]:
        """Write multiple spans."""
        span_ids = []

        for span_data in spans:
            span_id = await self.write_span(
                project_id=UUID(span_data["project_id"]),
                trace_id=UUID(span_data["trace_id"]),
                service=span_data["service"],
                operation_name=span_data["operation_name"],
                status=SpanStatus(span_data["status"]),
                start_time=span_data["start_time"],
                end_time=span_data["end_time"],
                parent_span_id=UUID(span_data["parent_span_id"])
                if span_data.get("parent_span_id")
                else None,
                tags=span_data.get("tags"),
                logs=span_data.get("logs"),
            )
            span_ids.append(span_id)

        return span_ids


class TraceQueryEngine:
    """Queries distributed traces."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_trace(
        self, project_id: UUID, trace_id: UUID
    ) -> Optional[Trace]:
        """Get a complete trace with all spans."""
        stmt = select(TraceSpanModel).where(
            and_(
                TraceSpanModel.project_id == project_id,
                TraceSpanModel.trace_id == trace_id,
            )
        )

        result = await self.db.execute(stmt)
        spans = result.scalars().all()

        if not spans:
            return None

        # Convert to schema
        span_schemas = [
            TraceSpan(
                span_id=span.span_id,
                trace_id=span.trace_id,
                parent_span_id=span.parent_span_id,
                project_id=span.project_id,
                service=span.service,
                operation_name=span.operation_name,
                status=span.status,
                start_time=span.start_time,
                end_time=span.end_time,
                duration_ms=span.duration_ms,
                tags=span.tags,
                logs=span.logs,
            )
            for span in spans
        ]

        # Find root and calculate total duration
        root_span = next(
            (s for s in span_schemas if s.parent_span_id is None),
            span_schemas[0] if span_schemas else None,
        )

        if not root_span:
            return None

        total_duration = (root_span.end_time - root_span.start_time).total_seconds() * 1000

        return Trace(
            trace_id=trace_id,
            project_id=project_id,
            root_service=root_span.service,
            root_operation=root_span.operation_name,
            start_time=root_span.start_time,
            end_time=root_span.end_time,
            total_duration_ms=total_duration,
            span_count=len(span_schemas),
            spans=span_schemas,
        )

    async def search(
        self,
        project_id: UUID,
        service: Optional[str] = None,
        operation: Optional[str] = None,
        min_duration_ms: Optional[float] = None,
        max_duration_ms: Optional[float] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Trace]:
        """
        Search for traces with filters.

        Returns list of root spans matching criteria, converted to Trace objects.
        """
        # Get root spans (no parent)
        stmt = select(TraceSpanModel).where(
            and_(
                TraceSpanModel.project_id == project_id,
                TraceSpanModel.parent_span_id == None,
            )
        )

        if service:
            stmt = stmt.where(TraceSpanModel.service == service)

        if operation:
            stmt = stmt.where(
                TraceSpanModel.operation_name.icontains(operation)
            )

        if min_duration_ms:
            stmt = stmt.where(
                TraceSpanModel.duration_ms >= min_duration_ms
            )

        if max_duration_ms:
            stmt = stmt.where(
                TraceSpanModel.duration_ms <= max_duration_ms
            )

        if start_time:
            stmt = stmt.where(TraceSpanModel.start_time >= start_time)

        if end_time:
            stmt = stmt.where(TraceSpanModel.start_time <= end_time)

        stmt = stmt.order_by(
            desc(TraceSpanModel.start_time)
        ).limit(limit)

        result = await self.db.execute(stmt)
        root_spans = result.scalars().all()

        # Build complete traces for each root
        traces = []

        for root_span in root_spans:
            trace = await self.get_trace(project_id, root_span.trace_id)
            if trace:
                traces.append(trace)

        return traces
