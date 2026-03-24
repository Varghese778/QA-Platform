"""User Store - manages user records and IdP subject mapping."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import User, Membership
from auth_service.models.enums import UserStatus

logger = logging.getLogger(__name__)


class UserService:
    """
    Persists user records and maps IdP subject to platform user_id.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get a user by their UUID.

        Args:
            user_id: The user's UUID.

        Returns:
            User entity or None.
        """
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email.

        Args:
            email: User's email address.

        Returns:
            User entity or None.
        """
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idp_subject(
        self,
        idp_subject: str,
        idp_provider: str,
    ) -> Optional[User]:
        """
        Get a user by their IdP subject claim.

        Args:
            idp_subject: The IdP subject (sub claim).
            idp_provider: The IdP identifier.

        Returns:
            User entity or None.
        """
        stmt = select(User).where(
            User.idp_subject == idp_subject,
            User.idp_provider == idp_provider,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        idp_subject: str,
        idp_provider: str,
        email: str,
        name: str,
    ) -> User:
        """
        Create a new user (auto-provision on first login).

        Args:
            idp_subject: The IdP subject claim.
            idp_provider: The IdP identifier.
            email: User's email.
            name: User's display name.

        Returns:
            Created User entity.
        """
        user = User(
            idp_subject=idp_subject,
            idp_provider=idp_provider,
            email=email,
            name=name,
            status=UserStatus.ACTIVE,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info(f"Created new user {user.user_id} ({email})")
        return user

    async def get_or_create_user(
        self,
        idp_subject: str,
        idp_provider: str,
        email: str,
        name: str,
    ) -> tuple[User, bool]:
        """
        Get existing user or create new one (auto-provision).

        Args:
            idp_subject: The IdP subject claim.
            idp_provider: The IdP identifier.
            email: User's email.
            name: User's display name.

        Returns:
            Tuple of (User, was_created).
        """
        existing = await self.get_by_idp_subject(idp_subject, idp_provider)
        if existing:
            return existing, False

        user = await self.create_user(idp_subject, idp_provider, email, name)
        return user, True

    async def update_last_login(self, user_id: UUID) -> None:
        """
        Update user's last login timestamp.

        Args:
            user_id: The user's UUID.
        """
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)

    async def suspend_user(self, user_id: UUID) -> bool:
        """
        Suspend a user account.

        Args:
            user_id: The user's UUID.

        Returns:
            True if user was suspended.
        """
        stmt = (
            update(User)
            .where(User.user_id == user_id, User.status == UserStatus.ACTIVE)
            .values(status=UserStatus.SUSPENDED)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def get_user_organizations(self, user_id: UUID) -> list[UUID]:
        """
        Get list of organization IDs the user belongs to.

        Args:
            user_id: The user's UUID.

        Returns:
            List of org UUIDs.
        """
        from auth_service.models import Project

        stmt = (
            select(Project.org_id)
            .join(Membership, Membership.project_id == Project.project_id)
            .where(
                Membership.user_id == user_id,
                Membership.removed_at.is_(None),
            )
            .distinct()
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
