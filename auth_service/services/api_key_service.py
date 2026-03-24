"""API Key Manager - generates, hashes, and validates API keys."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import APIKey, User
from auth_service.utils import generate_api_key, verify_token_hash

logger = logging.getLogger(__name__)


class APIKeyService:
    """
    Generates, hashes, and validates programmatic API keys.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_api_key(
        self,
        user_id: UUID,
        description: str,
        expires_at: Optional[datetime] = None,
    ) -> tuple[APIKey, str]:
        """
        Create a new API key for a user.

        Args:
            user_id: The user's UUID.
            description: Purpose label for the key.
            expires_at: Optional expiration datetime.

        Returns:
            Tuple of (APIKey entity, raw_key_value).
            Note: raw_key is only returned once at creation.
        """
        raw_key, key_hash = generate_api_key()

        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            description=description,
            expires_at=expires_at,
        )
        self.db.add(api_key)
        await self.db.flush()

        logger.info(f"Created API key {api_key.api_key_id} for user {user_id}")
        return api_key, raw_key

    async def validate_api_key(self, raw_key: str) -> Optional[User]:
        """
        Validate an API key and return the associated user.

        Args:
            raw_key: The raw API key value.

        Returns:
            User entity if valid, None otherwise.
        """
        # Find all non-revoked API keys and check hash
        stmt = select(APIKey).where(APIKey.revoked == False)
        result = await self.db.execute(stmt)
        api_keys = result.scalars().all()

        for api_key in api_keys:
            if verify_token_hash(raw_key, api_key.key_hash):
                # Check expiration
                if api_key.expires_at and api_key.expires_at < datetime.now(
                    timezone.utc
                ):
                    logger.warning(f"API key {api_key.api_key_id} has expired")
                    return None

                # Update last_used_at
                api_key.last_used_at = datetime.now(timezone.utc)

                # Get user
                user_stmt = select(User).where(User.user_id == api_key.user_id)
                user_result = await self.db.execute(user_stmt)
                user = user_result.scalar_one_or_none()

                if user and user.status.value == "ACTIVE":
                    logger.info(
                        f"API key {api_key.api_key_id} validated for user {user.user_id}"
                    )
                    return user

                return None

        return None

    async def get_user_api_keys(self, user_id: UUID) -> list[APIKey]:
        """
        Get all API keys for a user (excluding revoked).

        Args:
            user_id: The user's UUID.

        Returns:
            List of APIKey entities.
        """
        stmt = select(APIKey).where(
            APIKey.user_id == user_id,
            APIKey.revoked == False,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_api_key(
        self,
        api_key_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[APIKey]:
        """
        Get an API key by ID.

        Args:
            api_key_id: The API key's UUID.
            user_id: Optional user ID to verify ownership.

        Returns:
            APIKey entity or None.
        """
        conditions = [APIKey.api_key_id == api_key_id]
        if user_id:
            conditions.append(APIKey.user_id == user_id)

        stmt = select(APIKey).where(*conditions)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_api_key(
        self,
        api_key_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """
        Revoke an API key.

        Args:
            api_key_id: The API key's UUID.
            user_id: Optional user ID to verify ownership.

        Returns:
            True if key was revoked.
        """
        api_key = await self.get_api_key(api_key_id, user_id)
        if not api_key:
            return False

        api_key.revoked = True

        logger.info(f"Revoked API key {api_key_id}")
        return True
