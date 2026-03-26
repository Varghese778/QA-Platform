"""Metrics collection and querying services."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import and_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from observability.models import MetricSample as MetricSampleModel
from observability.schemas.enums import MetricType
from observability.schemas.tasks import MetricSample, MetricResponse, MetricsResponse

logger = logging.getLogger(__name__)


class MetricsReceiver:
    """Receives and stores metrics from services."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_metric(
        self,
        project_id: UUID,
        service: str,
        metric_name: str,
        metric_type: MetricType,
        value: float,
        labels: Optional[dict] = None,
    ) -> UUID:
        """Write a metric sample."""
        metric_id = uuid4()

        sample = MetricSampleModel(
            metric_id=metric_id,
            project_id=project_id,
            service=service,
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            labels=labels or {},
            timestamp=datetime.now(timezone.utc),
        )

        self.db.add(sample)
        await self.db.flush()

        logger.debug(
            f"Recorded {metric_name}={value} from {service}"
        )
        return metric_id

    async def write_batch(
        self, metrics: List[dict]
    ) -> List[UUID]:
        """Write multiple metrics."""
        metric_ids = []

        for metric_data in metrics:
            metric_id = await self.write_metric(
                project_id=UUID(metric_data["project_id"]),
                service=metric_data["service"],
                metric_name=metric_data["metric_name"],
                metric_type=MetricType(metric_data["metric_type"]),
                value=float(metric_data["value"]),
                labels=metric_data.get("labels"),
            )
            metric_ids.append(metric_id)

        return metric_ids


class MetricsQueryEngine:
    """Queries metrics from storage."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def query(
        self,
        project_id: UUID,
        service: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        labels: Optional[dict] = None,
    ) -> MetricResponse:
        """
        Query metrics for a time range.

        Args:
            project_id: Project ID
            service: Service name
            metric_name: Metric name
            start_time: Start time
            end_time: End time
            labels: Label filters

        Returns:
            MetricResponse with values
        """
        stmt = select(MetricSampleModel).where(
            and_(
                MetricSampleModel.project_id == project_id,
                MetricSampleModel.service == service,
                MetricSampleModel.metric_name == metric_name,
                MetricSampleModel.timestamp >= start_time,
                MetricSampleModel.timestamp <= end_time,
            )
        )

        result = await self.db.execute(stmt)
        samples = result.scalars().all()

        # Convert to (timestamp, value) tuples
        values = [
            (sample.timestamp, sample.value)
            for sample in sorted(samples, key=lambda s: s.timestamp)
        ]

        return MetricResponse(
            metric_name=metric_name,
            values=values,
        )

    async def query_range(
        self,
        project_id: UUID,
        service: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        step_seconds: int = 60,
        labels: Optional[dict] = None,
    ) -> MetricsResponse:
        """
        Query metrics with aggregation by time steps.

        Returns MetricsResponse with aggregated values per step.
        """
        stmt = select(MetricSampleModel).where(
            and_(
                MetricSampleModel.project_id == project_id,
                MetricSampleModel.service == service,
                MetricSampleModel.metric_name == metric_name,
                MetricSampleModel.timestamp >= start_time,
                MetricSampleModel.timestamp <= end_time,
            )
        )

        result = await self.db.execute(stmt)
        samples = result.scalars().all()

        # Aggregate into time steps
        values = []
        current_time = start_time

        while current_time <= end_time:
            next_time = current_time + timedelta(seconds=step_seconds)

            # Get average value for this step
            step_samples = [
                s.value
                for s in samples
                if current_time <= s.timestamp < next_time
            ]

            avg_value = (
                sum(step_samples) / len(step_samples)
                if step_samples
                else 0
            )

            values.append((current_time, avg_value))
            current_time = next_time

        metric_response = MetricResponse(
            metric_name=metric_name,
            values=values,
        )

        return MetricsResponse(
            metrics=[metric_response],
            total_points=len(values),
        )

    async def get_latest(
        self,
        project_id: UUID,
        service: str,
        metric_name: str,
    ) -> Optional[float]:
        """Get the latest value of a metric."""
        stmt = (
            select(MetricSampleModel)
            .where(
                and_(
                    MetricSampleModel.project_id == project_id,
                    MetricSampleModel.service == service,
                    MetricSampleModel.metric_name == metric_name,
                )
            )
            .order_by(desc(MetricSampleModel.timestamp))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        sample = result.scalar_one_or_none()

        return sample.value if sample else None
