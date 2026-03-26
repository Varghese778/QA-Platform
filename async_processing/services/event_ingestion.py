"""Event Ingestion API - receives events from producer services."""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from async_processing.config import get_settings
from async_processing.models import EventRecord
from async_processing.schemas.enums import EventStatus, EventPriority, EventType

logger = logging.getLogger(__name__)
settings = get_settings()


class EventIngestionAPI:
    """Handles event ingestion from producer services."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.redis = await redis.from_url(settings.redis_url)
        logger.info("EventIngestionAPI connected to Redis")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def ingest_event(
        self,
        project_id: UUID,
        event_type: EventType,
        source_service: str,
        data: dict,
        job_id: Optional[UUID] = None,
        priority: EventPriority = EventPriority.NORMAL,
        context: Optional[dict] = None,
    ) -> UUID:
        """
        Ingest a single event.

        Args:
            project_id: Project ID
            event_type: Type of event
            source_service: Service producing the event
            data: Event payload
            job_id: Associated job ID (optional)
            priority: Event priority
            context: Additional context (trace IDs, etc.)

        Returns:
            Event ID
        """
        event_id = uuid4()

        # Create event record
        event = EventRecord(
            event_id=event_id,
            project_id=project_id,
            job_id=job_id,
            event_type=event_type,
            source_service=source_service,
            data=data,
            priority=priority,
            status=EventStatus.PENDING,
            context=context or {},
        )

        self.db.add(event)
        await self.db.flush()

        logger.info(
            f"Ingested event {event_id} type={event_type.value} "
            f"from {source_service}"
        )

        # Publish to Redis Stream
        if self.redis:
            event_message = {
                "event_id": str(event_id),
                "project_id": str(project_id),
                "job_id": str(job_id) if job_id else None,
                "event_type": event_type.value,
                "source_service": source_service,
                "priority": priority.value,
                "data": json.dumps(data),
                "context": json.dumps(context or {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            try:
                await self.redis.xadd(
                    settings.event_stream_name,
                    event_message,
                )
                logger.debug(f"Published event {event_id} to Redis Stream")
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}")
                # Event still persisted in DB, will be retried by consumer

        return event_id

    async def ingest_batch(
        self,
        events: List[dict],
    ) -> List[UUID]:
        """
        Ingest multiple events.

        Args:
            events: List of event dictionaries

        Returns:
            List of event IDs
        """
        event_ids = []

        for event_data in events:
            event_id = await self.ingest_event(
                project_id=UUID(event_data["project_id"]),
                event_type=EventType(event_data["event_type"]),
                source_service=event_data["source_service"],
                data=event_data.get("data", {}),
                job_id=UUID(event_data["job_id"])
                if event_data.get("job_id")
                else None,
                priority=EventPriority(
                    event_data.get("priority", EventPriority.NORMAL.value)
                ),
                context=event_data.get("context"),
            )
            event_ids.append(event_id)

        logger.info(f"Ingested batch of {len(event_ids)} events")
        return event_ids

    async def get_event(self, event_id: UUID, project_id: UUID):
        """Get an event record."""
        from sqlalchemy import and_, select

        stmt = select(EventRecord).where(
            and_(
                EventRecord.event_id == event_id,
                EventRecord.project_id == project_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_job_events(
        self, project_id: UUID, job_id: UUID, limit: int = 100, offset: int = 0
    ):
        """Get all events for a job."""
        from sqlalchemy import and_, select

        stmt = (
            select(EventRecord)
            .where(
                and_(
                    EventRecord.project_id == project_id,
                    EventRecord.job_id == job_id,
                )
            )
            .order_by(EventRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()
