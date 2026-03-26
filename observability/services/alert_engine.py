"""Alert engine - Rule evaluation and alert generation."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from observability.models import AlertRule as AlertRuleModel, AlertEvent as AlertEventModel, MetricSample as MetricSampleModel
from observability.schemas.enums import (
    ComparisonOperator,
    AlertStatus,
    AlertSeverity,
)
from observability.schemas.tasks import AlertEvent, AlertRule

logger = logging.getLogger(__name__)


class AlertEngine:
    """Evaluates alert rules and generates alert events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rule(
        self,
        project_id: UUID,
        name: str,
        metric_name: str,
        service: str,
        operator: ComparisonOperator,
        threshold: float,
        severity: AlertSeverity,
        description: Optional[str] = None,
        duration_seconds: int = 300,
    ) -> UUID:
        """Create an alert rule."""
        rule_id = uuid4()

        rule = AlertRuleModel(
            rule_id=rule_id,
            project_id=project_id,
            name=name,
            description=description,
            metric_name=metric_name,
            service=service,
            operator=operator,
            threshold=threshold,
            duration_seconds=duration_seconds,
            severity=severity,
            enabled=True,
        )

        self.db.add(rule)
        await self.db.flush()

        logger.info(f"Created alert rule {rule_id}: {name}")
        return rule_id

    async def get_rules(
        self, project_id: UUID, enabled_only: bool = True
    ) -> List[AlertRule]:
        """Get alert rules for a project."""
        stmt = select(AlertRuleModel).where(
            AlertRuleModel.project_id == project_id
        )

        if enabled_only:
            stmt = stmt.where(AlertRuleModel.enabled == True)

        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        return [
            AlertRule(
                rule_id=rule.rule_id,
                project_id=rule.project_id,
                name=rule.name,
                description=rule.description,
                metric_name=rule.metric_name,
                service=rule.service,
                operator=rule.operator,
                threshold=rule.threshold,
                duration_seconds=rule.duration_seconds,
                severity=rule.severity,
                enabled=rule.enabled,
                created_at=rule.created_at,
                updated_at=rule.updated_at,
            )
            for rule in rules
        ]

    async def evaluate_rules(self) -> int:
        """
        Evaluate all enabled rules and generate alerts if conditions are met.

        Returns:
            Count of new alerts generated
        """
        stmt = select(AlertRuleModel).where(
            AlertRuleModel.enabled == True
        )

        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        alerts_created = 0

        for rule in rules:
            # Get recent metrics for this rule
            lookback_time = datetime.now(timezone.utc) - timedelta(
                seconds=rule.duration_seconds
            )

            metric_stmt = select(MetricSampleModel).where(
                and_(
                    MetricSampleModel.project_id == rule.project_id,
                    MetricSampleModel.service == rule.service,
                    MetricSampleModel.metric_name == rule.metric_name,
                    MetricSampleModel.timestamp >= lookback_time,
                )
            )

            metric_result = await self.db.execute(metric_stmt)
            samples = metric_result.scalars().all()

            if not samples:
                continue

            # Check if condition is met
            values = [s.value for s in samples]
            latest_value = values[-1] if values else None

            if await self._check_condition(
                rule.operator, latest_value, rule.threshold
            ):
                # Check if alert already exists
                existing_alert = await self._get_recent_alert(
                    rule.rule_id
                )

                if not existing_alert:
                    # Create new alert
                    await self._create_alert_event(
                        rule, latest_value
                    )
                    alerts_created += 1

        logger.info(f"Evaluated {len(rules)} rules, created {alerts_created} alerts")
        return alerts_created

    async def _check_condition(
        self,
        operator: ComparisonOperator,
        value: Optional[float],
        threshold: float,
    ) -> bool:
        """Check if a condition is met."""
        if value is None:
            return False

        if operator == ComparisonOperator.EQ:
            return value == threshold
        elif operator == ComparisonOperator.NEQ:
            return value != threshold
        elif operator == ComparisonOperator.GT:
            return value > threshold
        elif operator == ComparisonOperator.GTE:
            return value >= threshold
        elif operator == ComparisonOperator.LT:
            return value < threshold
        elif operator == ComparisonOperator.LTE:
            return value <= threshold

        return False

    async def _get_recent_alert(
        self, rule_id: UUID
    ) -> Optional[AlertEventModel]:
        """Get active alert for a rule created in the last 15 minutes."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=15)

        stmt = (
            select(AlertEventModel)
            .where(
                and_(
                    AlertEventModel.rule_id == rule_id,
                    AlertEventModel.status == AlertStatus.ACTIVE,
                    AlertEventModel.triggered_at >= cutoff_time,
                )
            )
            .order_by(desc(AlertEventModel.triggered_at))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_alert_event(
        self,
        rule: AlertRuleModel,
        metric_value: Optional[float],
    ) -> UUID:
        """Create an alert event."""
        alert_id = uuid4()

        message = (
            f"Alert {rule.name}: {rule.metric_name} "
            f"({metric_value if metric_value else 'Unknown'}) "
            f"{rule.operator.value} {rule.threshold}"
        )

        event = AlertEventModel(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            project_id=rule.project_id,
            status=AlertStatus.ACTIVE,
            severity=rule.severity,
            message=message,
            metric_value=metric_value,
        )

        self.db.add(event)
        await self.db.flush()

        logger.warning(f"Created alert {alert_id}: {message}")
        return alert_id

    async def get_active_alerts(
        self, project_id: UUID
    ) -> List[AlertEvent]:
        """Get active alerts for a project."""
        stmt = select(AlertEventModel).where(
            and_(
                AlertEventModel.project_id == project_id,
                AlertEventModel.status == AlertStatus.ACTIVE,
            )
        )

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return [
            AlertEvent(
                alert_id=event.alert_id,
                rule_id=event.rule_id,
                project_id=event.project_id,
                status=event.status,
                severity=event.severity,
                message=event.message,
                triggered_at=event.triggered_at,
                resolved_at=event.resolved_at,
                silenced_until=event.silenced_until,
                metric_value=event.metric_value,
                context=event.context,
            )
            for event in events
        ]

    async def resolve_alert(
        self, alert_id: UUID, project_id: UUID
    ) -> bool:
        """Resolve an alert."""
        stmt = select(AlertEventModel).where(
            and_(
                AlertEventModel.alert_id == alert_id,
                AlertEventModel.project_id == project_id,
            )
        )

        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            return False

        event.status = AlertStatus.RESOLVED
        event.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"Resolved alert {alert_id}")
        return True
