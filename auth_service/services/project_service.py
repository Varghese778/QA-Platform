"""Project Store - manages project records."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import Project, Membership
from auth_service.models.enums import ProjectStatus

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Persists project records and manages project creation/deletion.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """
        Get a project by ID.

        Args:
            project_id: The project's UUID.

        Returns:
            Project entity or None.
        """
        stmt = select(Project).where(
            Project.project_id == project_id,
            Project.status != ProjectStatus.DELETED,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_project(
        self,
        name: str,
        org_id: UUID,
        description: Optional[str] = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            name: Project name.
            org_id: Owning organization ID.
            description: Optional description.

        Returns:
            Created Project entity.
        """
        project = Project(
            name=name,
            org_id=org_id,
            description=description,
            status=ProjectStatus.ACTIVE,
        )
        self.db.add(project)
        await self.db.flush()

        logger.info(f"Created project {project.project_id} ({name})")
        return project

    async def delete_project(self, project_id: UUID) -> bool:
        """
        Soft delete a project.

        Args:
            project_id: The project's UUID.

        Returns:
            True if project was deleted.
        """
        project = await self.get_by_id(project_id)
        if not project:
            return False

        project.status = ProjectStatus.DELETED
        project.deleted_at = datetime.now(timezone.utc)

        logger.info(f"Soft deleted project {project_id}")
        return True

    async def get_user_projects(self, user_id: UUID) -> list[Project]:
        """
        Get all projects a user is a member of.

        Args:
            user_id: The user's UUID.

        Returns:
            List of Project entities.
        """
        stmt = (
            select(Project)
            .join(Membership, Membership.project_id == Project.project_id)
            .where(
                Membership.user_id == user_id,
                Membership.removed_at.is_(None),
                Project.status != ProjectStatus.DELETED,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_member_count(self, project_id: UUID) -> int:
        """
        Get the count of active members in a project.

        Args:
            project_id: The project's UUID.

        Returns:
            Number of active members.
        """
        stmt = select(func.count(Membership.membership_id)).where(
            Membership.project_id == project_id,
            Membership.removed_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
