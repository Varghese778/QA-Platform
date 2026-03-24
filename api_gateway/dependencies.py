"""FastAPI dependencies for the API Gateway."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api_gateway.core.jwt_validator import JWTValidator, JWTValidationError
from api_gateway.core.rate_limiter import RateLimiter, get_redis
from api_gateway.core.proxy_client import ProxyClient, get_proxy_client
from api_gateway.core.rbac_enforcer import RBACEnforcer

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
bearer_scheme = HTTPBearer(auto_error=False)

# Global instances
_jwt_validator: Optional[JWTValidator] = None
_rate_limiter: Optional[RateLimiter] = None
_rbac_enforcer: Optional[RBACEnforcer] = None


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user."""

    user_id: str
    email: Optional[str]
    name: Optional[str]
    roles: Dict[str, str]  # project_id -> role
    jti: Optional[str]  # Token ID

    def has_project_role(self, project_id: str, required_roles: Set[str]) -> bool:
        """Check if user has one of the required roles in a project."""
        user_role = self.roles.get(project_id)
        if not user_role:
            return False
        return user_role in required_roles

    def get_project_role(self, project_id: str) -> Optional[str]:
        """Get user's role in a specific project."""
        return self.roles.get(project_id)


async def get_jwt_validator() -> JWTValidator:
    """Get or create JWT validator."""
    global _jwt_validator
    if _jwt_validator is None:
        _jwt_validator = JWTValidator()
        await _jwt_validator.initialize()
    return _jwt_validator


async def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        redis_client = await get_redis()
        _rate_limiter = RateLimiter(redis_client)
    return _rate_limiter


def get_rbac_enforcer() -> RBACEnforcer:
    """Get or create RBAC enforcer."""
    global _rbac_enforcer
    if _rbac_enforcer is None:
        _rbac_enforcer = RBACEnforcer()
    return _rbac_enforcer


def get_proxy() -> ProxyClient:
    """Get proxy client."""
    return get_proxy_client()


async def get_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """
    Validate JWT and return authenticated user.

    This is the main authentication dependency for protected routes.

    Raises:
        HTTPException: 401 if authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        jwt_validator = await get_jwt_validator()
        payload = await jwt_validator.validate_token(token)
        claims = jwt_validator.extract_claims(payload)
    except JWTValidationError as e:
        request.state.error_code = e.code
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = AuthenticatedUser(
        user_id=claims["user_id"],
        email=claims.get("email"),
        name=claims.get("name"),
        roles=claims.get("roles", {}),
        jti=claims.get("jti"),
    )

    # Store in request state for access logging
    request.state.caller_id = user.user_id

    return user


async def check_project_permission(
    user: AuthenticatedUser,
    project_id: str,
    required_roles: Set[str],
    request: Request,
) -> None:
    """
    Check if user has required role in project.

    Raises:
        HTTPException: 403 if permission denied
    """
    if not user.has_project_role(project_id, required_roles):
        user_role = user.get_project_role(project_id)
        if user_role is None:
            detail = f"Not a member of project {project_id}"
        else:
            detail = f"Role '{user_role}' does not have permission for this operation"

        request.state.error_code = "INSUFFICIENT_PERMISSIONS"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> Optional[AuthenticatedUser]:
    """
    Optional authentication - returns None if no valid token.

    Use for routes that can work with or without authentication.
    """
    if not credentials:
        return None

    try:
        return await get_authenticated_user(request, credentials)
    except HTTPException:
        return None


# Cleanup function for application shutdown
async def cleanup_dependencies() -> None:
    """Clean up global instances on shutdown."""
    global _jwt_validator, _rate_limiter

    from api_gateway.core.rate_limiter import close_redis
    from api_gateway.core.proxy_client import close_proxy_client

    await close_redis()
    await close_proxy_client()

    _jwt_validator = None
    _rate_limiter = None
