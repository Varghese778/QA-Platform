"""Retention Manager - Record expiration and archival."""

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_layer.config import get_settings
from memory_layer.models import MemoryRecord

logger = logging.getLogger(__name__)
settings = get_settings()


class RetentionManager:
    """Manages record retention, expiration, and archival."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def archive_expired_records(self) -> int:
        """
        Archive records that have exceeded their expiration time.

        Returns:
            Count of records archived.
        """
        now = datetime.now(timezone.utc)

        # Get expired records
        stmt = select(MemoryRecord).where(
            and_(
                MemoryRecord.expires_at <= now,
                MemoryRecord.archived == False,
            )
        )

        result = await self.db.execute(stmt)
        expired = result.scalars().all()

        # Archive them
        for record in expired:
            record.archived = True

        await self.db.flush()
        count = len(expired)

        logger.info(f"Archived {count} expired records")
        return count

    async def hard_delete_archived_records() -> int:
        """
        Permanently delete records archived for longer than hard_delete_days.

        Returns:
            Count of records deleted.
        """
        cutoff = datetime.now(timezone.utc)
        buffer_days = settings.hard_delete_days

        # Records archived more than buffer_days ago
        # We use updated_at as proxy for archival time
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=buffer_days)

        stmt = select(MemoryRecord).where(
            and_(
                MemoryRecord.archived == True,
                MemoryRecord.updated_at <= cutoff,
            )
        )

        result = await self.db.execute(stmt)
        to_delete = result.scalars().all()

        # Hard delete
        for record in to_delete:
            await self.db.delete(record)

        await self.db.flush()
        count = len(to_delete)

        logger.info(f"Hard deleted {count} archived records")
        return count

    async def set_expiration(
        self,
        record_id: str,
        retention_days: int,
    ) -> bool:
        """
        Set expiration date for a record.

        Args:
            record_id: Record to expire
            retention_days: Days until expiration

        Returns:
            True if updated, False if not found
        """
        from uuid import UUID

        stmt = select(MemoryRecord).where(MemoryRecord.record_id == UUID(record_id))
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return False

        from datetime import timedelta

        now = datetime.now(timezone.utc)
        record.expires_at = now + timedelta(days=retention_days)
        await self.db.flush()

        logger.info(
            f"Set expiration for record {record_id} to {record.expires_at}"
        )
        return True
