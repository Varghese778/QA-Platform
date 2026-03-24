"""Token Issuer - mints JWT access tokens and refresh tokens."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config import get_settings
from auth_service.models import RefreshToken, User, Membership
from auth_service.utils import create_access_token, generate_refresh_token, hash_token

logger = logging.getLogger(__name__)
settings = get_settings()


class TokenIssuer:
    """
    Mints JWT access tokens with role claims and issues opaque refresh tokens.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_roles(self, user_id: uuid.UUID) -> Dict[str, str]:
        """
        Get all project roles for a user.

        Args:
            user_id: The user's UUID.

        Returns:
            Dict mapping project_id (str) to role name.
        """
        stmt = select(Membership).where(
            Membership.user_id == user_id,
            Membership.removed_at.is_(None),
        )
        result = await self.db.execute(stmt)
        memberships = result.scalars().all()

        return {
            str(m.project_id): m.role.value
            for m in memberships
        }

    async def issue_tokens(
        self,
        user: User,
    ) -> Tuple[str, str, int]:
        """
        Issue a new access token and refresh token pair.

        Args:
            user: The User entity to issue tokens for.

        Returns:
            Tuple of (access_token, refresh_token, expires_in_seconds).
        """
        # Get user's roles across all projects
        roles = await self.get_user_roles(user.user_id)

        # Create access token
        access_token = create_access_token(
            user_id=user.user_id,
            email=user.email,
            name=user.name,
            roles=roles,
        )

        # Create refresh token
        raw_refresh, token_hash = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_ttl_days
        )

        refresh_token_record = RefreshToken(
            user_id=user.user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(refresh_token_record)
        await self.db.flush()

        logger.info(
            f"Issued tokens for user {user.user_id}, "
            f"refresh_token_id={refresh_token_record.token_id}"
        )

        return access_token, raw_refresh, settings.jwt_access_token_ttl_seconds

    async def issue_access_token_only(
        self,
        user: User,
    ) -> Tuple[str, int]:
        """
        Issue only an access token (for API key authentication).

        Args:
            user: The User entity to issue token for.

        Returns:
            Tuple of (access_token, expires_in_seconds).
        """
        roles = await self.get_user_roles(user.user_id)

        access_token = create_access_token(
            user_id=user.user_id,
            email=user.email,
            name=user.name,
            roles=roles,
        )

        return access_token, settings.jwt_access_token_ttl_seconds

    async def refresh_tokens(
        self,
        raw_refresh_token: str,
    ) -> Optional[Tuple[str, str, int, uuid.UUID]]:
        """
        Validate a refresh token and issue new token pair (rotation).

        Args:
            raw_refresh_token: The raw opaque refresh token.

        Returns:
            Tuple of (access_token, new_refresh_token, expires_in, user_id)
            or None if refresh fails.
        """
        token_hash = hash_token(raw_refresh_token)

        # Find the refresh token
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        old_token = result.scalar_one_or_none()

        if not old_token:
            logger.warning("Refresh token not found")
            return None

        # Check if already revoked (potential replay attack)
        if old_token.revoked:
            logger.warning(
                f"Attempt to reuse revoked refresh token {old_token.token_id}. "
                "Potential replay attack detected."
            )
            # Revoke entire token family would be implemented here
            return None

        # Check expiry
        if old_token.expires_at < datetime.now(timezone.utc):
            logger.warning(f"Refresh token {old_token.token_id} has expired")
            return None

        # Get user
        stmt = select(User).where(User.user_id == old_token.user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or user.status != "ACTIVE":
            logger.warning(f"User {old_token.user_id} not found or not active")
            return None

        # Issue new tokens
        access_token, new_refresh, expires_in = await self.issue_tokens(user)

        # Mark old token as revoked and set rotated_to
        # Get the new token's ID
        new_token_hash = hash_token(new_refresh)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == new_token_hash)
        result = await self.db.execute(stmt)
        new_token = result.scalar_one()

        old_token.revoked = True
        old_token.rotated_to = new_token.token_id

        logger.info(
            f"Rotated refresh token {old_token.token_id} -> {new_token.token_id}"
        )

        return access_token, new_refresh, expires_in, user.user_id

    async def revoke_refresh_token(self, raw_refresh_token: str) -> bool:
        """
        Revoke a refresh token.

        Args:
            raw_refresh_token: The raw opaque refresh token.

        Returns:
            True if token was revoked, False if not found.
        """
        token_hash = hash_token(raw_refresh_token)

        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        token = result.scalar_one_or_none()

        if not token:
            return False

        token.revoked = True
        logger.info(f"Revoked refresh token {token.token_id}")
        return True

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            user_id: The user's UUID.

        Returns:
            Number of tokens revoked.
        """
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
        )
        result = await self.db.execute(stmt)
        tokens = result.scalars().all()

        count = 0
        for token in tokens:
            token.revoked = True
            count += 1

        logger.info(f"Revoked {count} refresh tokens for user {user_id}")
        return count
