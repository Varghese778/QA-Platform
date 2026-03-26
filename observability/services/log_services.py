"""Log collection and querying services."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from observability.models import LogEntry as LogEntryModel
from observability.schemas.enums import LogLevel
from observability.schemas.tasks import LogEntry, LogQuery, LogResponse

logger = logging.getLogger(__name__)


class LogCollector:
    """Collects and stores logs from services."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_log(
        self,
        project_id: UUID,
        service: str,
        level: LogLevel,
        message: str,
        trace_id: Optional[UUID] = None,
        context: Optional[dict] = None,
    ) -> UUID:
        """
        Write a log entry.

        Args:
            project_id: Project ID
            service: Source service name
            level: Log level
            message: Log message
            trace_id: Optional associated trace ID
            context: Additional context

        Returns:
            Log ID
        """
        log_id = uuid4()

        log_entry = LogEntryModel(
            log_id=log_id,
            project_id=project_id,
            service=service,
            level=level,
            message=message,
            trace_id=trace_id,
            context=context or {},
            timestamp=datetime.now(timezone.utc),
        )

        self.db.add(log_entry)
        await self.db.flush()

        logger.debug(
            f"Logged {level.value} from {service}: {message[:50]}"
        )
        return log_id

    async def write_batch(
        self,
        logs: List[dict],
    ) -> List[UUID]:
        """Write multiple logs."""
        log_ids = []

        for log_data in logs:
            log_id = await self.write_log(
                project_id=UUID(log_data["project_id"]),
                service=log_data["service"],
                level=LogLevel(log_data["level"]),
                message=log_data["message"],
                trace_id=UUID(log_data["trace_id"])
                if log_data.get("trace_id")
                else None,
                context=log_data.get("context"),
            )
            log_ids.append(log_id)

        return log_ids


class LogQueryEngine:
    """Queries logs from storage."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def query(
        self,
        project_id: UUID,
        service: Optional[str] = None,
        level: Optional[LogLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> LogResponse:
        """
        Query logs with filters.

        Args:
            project_id: Project ID
            service: Filter by service
            level: Filter by level
            start_time: Start time filter
            end_time: End time filter
            search_text: Full-text search in message
            limit: Result limit
            offset: Result offset

        Returns:
            LogResponse with results
        """
        stmt = select(LogEntryModel).where(
            LogEntryModel.project_id == project_id
        )

        if service:
            stmt = stmt.where(LogEntryModel.service == service)

        if level:
            stmt = stmt.where(LogEntryModel.level == level)

        if start_time:
            stmt = stmt.where(LogEntryModel.timestamp >= start_time)

        if end_time:
            stmt = stmt.where(LogEntryModel.timestamp <= end_time)

        if search_text:
            stmt = stmt.where(
                LogEntryModel.message.icontains(search_text)
            )

        # Get total count
        count_stmt = stmt
        count_result = await self.db.execute(
            select(LogEntryModel).where(*count_stmt.whereclause.clauses)
            if count_stmt.whereclause is not None
            else select(LogEntryModel)
        )
        total_count = len(count_result.scalars().all())

        # Apply pagination and ordering
        stmt = stmt.order_by(desc(LogEntryModel.timestamp)).offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        log_schemas = [
            LogEntry(
                log_id=log.log_id,
                project_id=log.project_id,
                service=log.service,
                level=log.level,
                message=log.message,
                timestamp=log.timestamp,
                trace_id=log.trace_id,
                context=log.context,
                version=log.version,
            )
            for log in logs
        ]

        return LogResponse(
            logs=log_schemas,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    async def get_by_trace_id(
        self, project_id: UUID, trace_id: UUID
    ) -> List[LogEntry]:
        """Get all logs for a trace."""
        stmt = select(LogEntryModel).where(
            and_(
                LogEntryModel.project_id == project_id,
                LogEntryModel.trace_id == trace_id,
            )
        )

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        return [
            LogEntry(
                log_id=log.log_id,
                project_id=log.project_id,
                service=log.service,
                level=log.level,
                message=log.message,
                timestamp=log.timestamp,
                trace_id=log.trace_id,
                context=log.context,
                version=log.version,
            )
            for log in logs
        ]
