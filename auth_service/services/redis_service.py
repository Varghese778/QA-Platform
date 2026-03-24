"""Redis service for token revocation denylist and invitation tokens."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import redis.asyncio as redis

from auth_service.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global Redis connection pool
_redis_pool: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None


class TokenDenylistService:
    """
    Manages the token revocation denylist in Redis.

    Revoked access tokens are added to the denylist with TTL matching
    their remaining lifetime.
    """

    DENYLIST_PREFIX = "token:revoked:"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def add_to_denylist(
        self,
        token_jti: str,
        expires_at: datetime,
    ) -> bool:
        """
        Add a token to the revocation denylist.

        Args:
            token_jti: The JWT ID (jti claim).
            expires_at: Token expiration time.

        Returns:
            True if added successfully.
        """
        key = f"{self.DENYLIST_PREFIX}{token_jti}"

        # Calculate TTL (remaining token lifetime)
        now = datetime.now(timezone.utc)
        ttl_seconds = int((expires_at - now).total_seconds())

        if ttl_seconds <= 0:
            # Token already expired, no need to denylist
            return True

        try:
            await self.redis.setex(key, ttl_seconds, "1")
            logger.info(f"Added token {token_jti} to denylist with TTL {ttl_seconds}s")
            return True
        except Exception as e:
            logger.error(f"Failed to add token to denylist: {e}")
            raise

    async def is_token_revoked(self, token_jti: str) -> bool:
        """
        Check if a token is in the revocation denylist.

        Args:
            token_jti: The JWT ID (jti claim).

        Returns:
            True if token is revoked.
        """
        key = f"{self.DENYLIST_PREFIX}{token_jti}"
        try:
            result = await self.redis.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to check denylist: {e}")
            # Fail closed: if Redis is unavailable, reject the token
            raise


class InvitationService:
    """
    Manages project invitation tokens in Redis.

    Invitation tokens are single-use and expire after 7 days.
    """

    INVITATION_PREFIX = "invitation:"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def create_invitation(
        self,
        invitation_id: UUID,
        invitation_token: str,
        project_id: UUID,
        email: str,
        role: str,
        invited_by: UUID,
    ) -> datetime:
        """
        Create a new invitation token.

        Args:
            invitation_id: Unique invitation ID.
            invitation_token: The opaque invitation token.
            project_id: Project to invite to.
            email: Invitee email.
            role: Role to assign.
            invited_by: User who created the invitation.

        Returns:
            Expiration datetime.
        """
        key = f"{self.INVITATION_PREFIX}{invitation_token}"
        ttl_seconds = settings.invitation_token_ttl_days * 24 * 60 * 60
        expires_at = datetime.now(timezone.utc).timestamp() + ttl_seconds

        data = {
            "invitation_id": str(invitation_id),
            "project_id": str(project_id),
            "email": email,
            "role": role,
            "invited_by": str(invited_by),
            "expires_at": expires_at,
        }

        await self.redis.setex(key, ttl_seconds, json.dumps(data))
        logger.info(f"Created invitation {invitation_id} for {email}")

        return datetime.fromtimestamp(expires_at, tz=timezone.utc)

    async def get_invitation(
        self,
        invitation_token: str,
    ) -> Optional[dict]:
        """
        Get invitation data and validate it.

        Args:
            invitation_token: The invitation token.

        Returns:
            Invitation data dict or None if invalid/expired.
        """
        key = f"{self.INVITATION_PREFIX}{invitation_token}"

        try:
            data = await self.redis.get(key)
            if not data:
                return None

            invitation = json.loads(data)

            # Check expiration
            if invitation["expires_at"] < datetime.now(timezone.utc).timestamp():
                await self.redis.delete(key)
                return None

            return invitation
        except Exception as e:
            logger.error(f"Failed to get invitation: {e}")
            return None

    async def consume_invitation(self, invitation_token: str) -> Optional[dict]:
        """
        Get and delete an invitation (single-use).

        Args:
            invitation_token: The invitation token.

        Returns:
            Invitation data dict or None if invalid.
        """
        key = f"{self.INVITATION_PREFIX}{invitation_token}"

        try:
            # Use GETDEL for atomic get-and-delete
            data = await self.redis.getdel(key)
            if not data:
                return None

            invitation = json.loads(data)

            if invitation["expires_at"] < datetime.now(timezone.utc).timestamp():
                return None

            logger.info(f"Consumed invitation {invitation['invitation_id']}")
            return invitation
        except Exception as e:
            logger.error(f"Failed to consume invitation: {e}")
            return None


class BruteForceProtection:
    """
    Tracks failed login attempts for brute-force protection.
    """

    ATTEMPTS_PREFIX = "login:attempts:"
    LOCKOUT_PREFIX = "login:lockout:"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def record_failed_attempt(self, user_identifier: str) -> int:
        """
        Record a failed login attempt.

        Args:
            user_identifier: User email or ID.

        Returns:
            Current attempt count.
        """
        key = f"{self.ATTEMPTS_PREFIX}{user_identifier}"
        window_seconds = settings.brute_force_window_minutes * 60

        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

        count = results[0]

        if count >= settings.brute_force_max_attempts:
            await self._lock_account(user_identifier)

        return count

    async def _lock_account(self, user_identifier: str) -> None:
        """Lock an account due to too many failed attempts."""
        key = f"{self.LOCKOUT_PREFIX}{user_identifier}"
        lockout_seconds = settings.brute_force_lockout_minutes * 60

        await self.redis.setex(key, lockout_seconds, "1")
        logger.warning(f"Account locked due to brute-force: {user_identifier}")

    async def is_locked(self, user_identifier: str) -> bool:
        """Check if an account is locked."""
        key = f"{self.LOCKOUT_PREFIX}{user_identifier}"
        result = await self.redis.exists(key)
        return bool(result)

    async def clear_attempts(self, user_identifier: str) -> None:
        """Clear failed attempts after successful login."""
        key = f"{self.ATTEMPTS_PREFIX}{user_identifier}"
        await self.redis.delete(key)
