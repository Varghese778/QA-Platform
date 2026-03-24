"""Membership Store - manages project membership and roles."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import Membership, User
from auth_service.models.enums import ProjectRole

logger = logging.getLogger(__name__)


class MembershipService:
    """
    Persists project membership with role assignments.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_membership(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> Optional[Membership]:
        """
        Get a user's membership in a project.

        Args:
            project_id: The project's UUID.
            user_id: The user's UUID.

        Returns:
            Membership entity or None.
        """
        stmt = select(Membership).where(
            Membership.project_id == project_id,
            Membership.user_id == user_id,
            Membership.removed_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(
        self,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
        added_by: Optional[UUID] = None,
    ) -> Membership:
        """
        Add a user to a project with a role.

        Args:
            project_id: The project's UUID.
            user_id: The user's UUID.
            role: The role to assign.
            added_by: UUID of user who added this member.

        Returns:
            Created Membership entity.
        """
        membership = Membership(
            project_id=project_id,
            user_id=user_id,
            role=role,
            added_by=added_by,
        )
        self.db.add(membership)
        await self.db.flush()

        logger.info(
            f"Added user {user_id} to project {project_id} with role {role.value}"
        )
        return membership

    async def update_role(
        self,
        project_id: UUID,
        user_id: UUID,
        new_role: ProjectRole,
    ) -> Optional[Membership]:
        """
        Update a user's role in a project.

        Args:
            project_id: The project's UUID.
            user_id: The user's UUID.
            new_role: The new role to assign.

        Returns:
            Updated Membership entity or None if not found.
        """
        membership = await self.get_membership(project_id, user_id)
        if not membership:
            return None

        old_role = membership.role
        membership.role = new_role

        logger.info(
            f"Updated role for user {user_id} in project {project_id}: "
            f"{old_role.value} -> {new_role.value}"
        )
        return membership

    async def remove_member(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Soft remove a user from a project.

        Args:
            project_id: The project's UUID.
            user_id: The user's UUID.

        Returns:
            True if member was removed.
        """
        membership = await self.get_membership(project_id, user_id)
        if not membership:
            return False

        membership.removed_at = datetime.now(timezone.utc)

        logger.info(f"Removed user {user_id} from project {project_id}")
        return True

    async def get_project_members(
        self,
        project_id: UUID,
    ) -> list[tuple[Membership, User]]:
        """
        Get all members of a project with user details.

        Args:
            project_id: The project's UUID.

        Returns:
            List of (Membership, User) tuples.
        """
        stmt = (
            select(Membership, User)
            .join(User, Membership.user_id == User.user_id)
            .where(
                Membership.project_id == project_id,
                Membership.removed_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def count_admins(self, project_id: UUID) -> int:
        """
        Count the number of PROJECT_ADMIN members in a project.

        Args:
            project_id: The project's UUID.

        Returns:
            Number of admins.
        """
        stmt = select(Membership).where(
            Membership.project_id == project_id,
            Membership.role == ProjectRole.PROJECT_ADMIN,
            Membership.removed_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return len(result.scalars().all())

    async def is_last_admin(self, project_id: UUID, user_id: UUID) -> bool:
        """
        Check if a user is the last PROJECT_ADMIN in a project.

        Args:
            project_id: The project's UUID.
            user_id: The user's UUID.

        Returns:
            True if user is the only admin.
        """
        membership = await self.get_membership(project_id, user_id)
        if not membership or membership.role != ProjectRole.PROJECT_ADMIN:
            return False

        admin_count = await self.count_admins(project_id)
        return admin_count == 1

    async def check_membership(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a user is a member of a project.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.

        Returns:
            Tuple of (is_member, role_value).
        """
        membership = await self.get_membership(project_id, user_id)
        if membership:
            return True, membership.role.value
        return False, None
