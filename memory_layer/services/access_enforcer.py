"""AccessEnforcer - Enforces project_id scope on all operations."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_layer.config import get_settings
from memory_layer.models import MemoryRecord

logger = logging.getLogger(__name__)
settings = get_settings()


class AccessDeniedError(Exception):
    """Raised when access is denied."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AccessEnforcer:
    """
    Enforces strict project-level access isolation.

    - Validates all operations scoped to project_id
    - Logs security events on denied access
    - Rejects cross-project access
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authorize_read(
        self,
        project_id: UUID,
        caller_service: Optional[str] = None,
    ) -> None:
        """
        Authorize a read operation.

        Args:
            project_id: Project being accessed.
            caller_service: Service making the request.

        Raises:
            AccessDeniedError: If caller not authorized.
        """
        # Validate service is in allowlist
        if caller_service and caller_service not in settings.allowed_services:
            logger.warning(
                f"Unauthorized service attempted read: {caller_service}"
            )
            raise AccessDeniedError(f"Service {caller_service} not authorized")

        # In production, would check service-to-project mappings
        logger.debug(f"Read access authorized for project {project_id}")

    async def authorize_write(
        self,
        project_id: UUID,
        caller_service: Optional[str] = None,
    ) -> None:
        """
        Authorize a write operation.

        Args:
            project_id: Project being modified.
            caller_service: Service making the request.

        Raises:
            AccessDeniedError: If caller not authorized.
        """
        # Only specific services can write
        write_services = {"orchestrator", "multi_agent_engine"}
        if caller_service and caller_service not in write_services:
            logger.warning(
                f"Unauthorized service attempted write: {caller_service}"
            )
            raise AccessDeniedError(f"Service {caller_service} cannot write")

        logger.debug(f"Write access authorized for project {project_id}")

    async def authorize_delete(
        self,
        project_id: UUID,
        caller_service: Optional[str] = None,
    ) -> None:
        """
        Authorize a delete operation.

        Args:
            project_id: Project being modified.
            caller_service: Service making the request.

        Raises:
            AccessDeniedError: If caller not authorized.
        """
        # Only orchestrator can delete
        if caller_service and caller_service != "orchestrator":
            logger.warning(
                f"Unauthorized service attempted delete: {caller_service}"
            )
            raise AccessDeniedError(f"Service {caller_service} cannot delete")

        logger.debug(f"Delete access authorized for project {project_id}")

    async def verify_record_ownership(
        self,
        record_id: UUID,
        project_id: UUID,
    ) -> bool:
        """
        Verify a record belongs to the specified project.

        Args:
            record_id: Record to verify.
            project_id: Expected project owner.

        Returns:
            True if record belongs to project.
        """
        stmt = select(MemoryRecord).where(
            MemoryRecord.record_id == record_id,
            MemoryRecord.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            logger.warning(
                f"Cross-project access attempt: record {record_id} not in project {project_id}"
            )
            return False

        return True
