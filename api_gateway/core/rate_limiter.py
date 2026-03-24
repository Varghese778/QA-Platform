"""Rate Limiter - Sliding window rate limiter backed by Redis."""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import redis.asyncio as redis

from api_gateway.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        limit: int,
        remaining: int,
        reset_at: int,
        limit_type: str,
    ):
        self.limit = limit
        self.remaining = remaining
        self.reset_at = reset_at
        self.limit_type = limit_type
        super().__init__(f"Rate limit exceeded for {limit_type}")


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    limit_type: str  # "user" or "project"


class RateLimiter:
    """
    Sliding window rate limiter using Redis.

    Maintains per-user and per-project counters with configurable limits.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        user_limit: Optional[int] = None,
        project_limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        fail_open: Optional[bool] = None,
    ):
        self.redis = redis_client
        self.user_limit = user_limit or settings.rate_limit_user_per_minute
        self.project_limit = project_limit or settings.rate_limit_project_per_minute
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds
        self.fail_open = fail_open if fail_open is not None else settings.rate_limit_fail_open

    def _get_window_key(self, identifier_type: str, identifier: str) -> str:
        """Generate Redis key for rate limit window."""
        window = int(time.time()) // self.window_seconds
        return f"rl:{identifier_type}:{identifier}:{window}"

    async def _check_limit(
        self,
        identifier_type: str,
        identifier: str,
        limit: int,
    ) -> RateLimitResult:
        """
        Check rate limit for an identifier.

        Uses INCR with TTL for sliding window approximation.
        """
        key = self._get_window_key(identifier_type, identifier)
        window_start = (int(time.time()) // self.window_seconds) * self.window_seconds
        reset_at = window_start + self.window_seconds

        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window_seconds + 1)  # +1 for safety margin
            results = await pipe.execute()
            current_count = results[0]
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            if self.fail_open:
                # Allow request but log warning
                logger.warning("Rate limiter failing open due to Redis error")
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit,
                    reset_at=reset_at,
                    limit_type=identifier_type,
                )
            else:
                # Fail closed - deny the request
                raise

        remaining = max(0, limit - current_count)
        allowed = current_count <= limit

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            limit_type=identifier_type,
        )

    async def check_user_limit(self, user_id: str) -> RateLimitResult:
        """Check rate limit for a user."""
        return await self._check_limit("user", user_id, self.user_limit)

    async def check_project_limit(self, project_id: str) -> RateLimitResult:
        """Check rate limit for a project."""
        return await self._check_limit("project", project_id, self.project_limit)

    async def check_limits(
        self,
        user_id: str,
        project_id: Optional[str] = None,
    ) -> Tuple[RateLimitResult, Optional[RateLimitResult]]:
        """
        Check both user and project rate limits.

        Args:
            user_id: The user identifier.
            project_id: Optional project identifier.

        Returns:
            Tuple of (user_result, project_result).

        Raises:
            RateLimitExceeded: If any limit is exceeded.
        """
        user_result = await self.check_user_limit(user_id)

        if not user_result.allowed:
            raise RateLimitExceeded(
                limit=user_result.limit,
                remaining=user_result.remaining,
                reset_at=user_result.reset_at,
                limit_type="user",
            )

        project_result = None
        if project_id:
            project_result = await self.check_project_limit(project_id)
            if not project_result.allowed:
                raise RateLimitExceeded(
                    limit=project_result.limit,
                    remaining=project_result.remaining,
                    reset_at=project_result.reset_at,
                    limit_type="project",
                )

        return user_result, project_result

    def get_headers(
        self,
        user_result: RateLimitResult,
        project_result: Optional[RateLimitResult] = None,
    ) -> dict:
        """
        Generate rate limit response headers.

        Uses the most restrictive limit if both are present.
        """
        # Use the result with lower remaining quota
        result = user_result
        if project_result and project_result.remaining < user_result.remaining:
            result = project_result

        return {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(result.reset_at),
        }


# Global Redis connection
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
