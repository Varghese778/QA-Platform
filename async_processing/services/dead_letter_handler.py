"""Dead Letter Handler and Replay Engine - handle failed events."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from async_processing.config import get_settings
from async_processing.models import DeadLetterEntry, EventRecord
from async_processing.schemas.enums import EventStatus, EventType

logger = logging.getLogger(__name__)
settings = get_settings()


class DeadLetterHandler:
    """Handles failed events and moves them to dead letter queue."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def move_to_dlq(
        self,
        event_id: UUID,
        project_id: UUID,
        reason: str,
    ) -> Optional[UUID]:
        """
        Move a failed event to dead letter queue.

        Args:
            event_id: Event ID
            project_id: Project ID
            reason: Reason for dead lettering

        Returns:
            Dead letter queue entry ID or None if event not found
        """
        # Get event
        stmt = select(EventRecord).where(
            and_(
                EventRecord.event_id == event_id,
                EventRecord.project_id == project_id,
            )
        )
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            logger.warning(f"Event {event_id} not found for DLQ")
            return None

        # Create DLQ entry
        from uuid import uuid4

        dlq_entry = DeadLetterEntry(
            dlq_id=uuid4(),
            original_event_id=event_id,
            project_id=project_id,
            job_id=event.job_id,
            event_type=event.event_type,
            reason=reason,
            retry_count=event.retry_count,
            data=event.data,
        )

        self.db.add(dlq_entry)
        await self.db.flush()

        logger.info(
            f"Moved event {event_id} to DLQ: {dlq_entry.dlq_id}"
        )
        return dlq_entry.dlq_id

    async def get_dlq_entries(
        self,
        project_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DeadLetterEntry]:
        """Get dead letter queue entries for a project."""
        stmt = (
            select(DeadLetterEntry)
            .where(DeadLetterEntry.project_id == project_id)
            .order_by(DeadLetterEntry.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def purge_old_dlq_entries(self) -> int:
        """
        Purge old dead letter queue entries beyond retention period.

        Returns:
            Number of entries purged
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.dead_letter_retention_days
        )

        # Get old entries
        stmt = select(DeadLetterEntry).where(
            DeadLetterEntry.created_at < cutoff
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        # Delete them
        for entry in entries:
            await self.db.delete(entry)

        await self.db.flush()

        logger.info(f"Purged {len(entries)} old DLQ entries")
        return len(entries)


class ReplayEngine:
    """Re-processes failed events from dead letter queue."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.dlq_handler = DeadLetterHandler(db)

    async def replay_event(
        self, dlq_id: UUID, project_id: UUID
    ) -> Optional[UUID]:
        """
        Replay a dead letter event as a new event.

        Args:
            dlq_id: Dead letter queue entry ID
            project_id: Project ID

        Returns:
            New event ID or None if replay failed
        """
        # Get DLQ entry
        stmt = select(DeadLetterEntry).where(
            and_(
                DeadLetterEntry.dlq_id == dlq_id,
                DeadLetterEntry.project_id == project_id,
            )
        )
        result = await self.db.execute(stmt)
        dlq_entry = result.scalar_one_or_none()

        if not dlq_entry:
            logger.warning(f"DLQ entry {dlq_id} not found")
            return None

        # Create new event from DLQ entry
        from uuid import uuid4

        new_event_id = uuid4()

        new_event = EventRecord(
            event_id=new_event_id,
            project_id=project_id,
            job_id=dlq_entry.job_id,
            event_type=dlq_entry.event_type,
            source_service="replay_engine",
            data=dlq_entry.data,
            status=EventStatus.PENDING,
        )

        self.db.add(new_event)
        await self.db.flush()

        # Update DLQ entry
        dlq_entry.retry_count += 1
        dlq_entry.last_retry_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            f"Replayed DLQ entry {dlq_id} as new event {new_event_id}"
        )
        return new_event_id

    async def replay_batch(
        self, dlq_ids: List[UUID], project_id: UUID
    ) -> List[UUID]:
        """
        Replay multiple dead letter events.

        Args:
            dlq_ids: List of DLQ entry IDs
            project_id: Project ID

        Returns:
            List of new event IDs
        """
        new_event_ids = []

        for dlq_id in dlq_ids:
            new_event_id = await self.replay_event(dlq_id, project_id)
            if new_event_id:
                new_event_ids.append(new_event_id)

        logger.info(f"Replayed {len(new_event_ids)} events")
        return new_event_ids

    async def should_retry(self, dlq_entry: DeadLetterEntry) -> bool:
        """Determine if an event should be retried."""
        if dlq_entry.retry_count >= settings.dead_letter_max_retries:
            logger.warning(
                f"DLQ entry {dlq_entry.dlq_id} exceeded max retries"
            )
            return False

        return True
