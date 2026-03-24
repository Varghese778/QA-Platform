"""FastAPI dependencies for authentication and service injection."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from auth_service.database import get_db_session
from auth_service.models import User
from auth_service.models.enums import UserStatus
from auth_service.services import (
    OIDCAuthHandler,
    TokenIssuer,
    RBACEngine,
    UserService,
    ProjectService,
    MembershipService,
    APIKeyService,
    AuditService,
    get_redis,
    TokenDenylistService,
    InvitationService,
    BruteForceProtection,
)
from auth_service.utils import decode_access_token
from auth_service.config import get_settings

settings = get_settings()

# HTTP Bearer security scheme
bearer_scheme = HTTPBearer(auto_error=False)


# Database session dependency
async def get_db() -> AsyncSession:
    """Get database session."""
    async for session in get_db_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


# Service dependencies
def get_oidc_handler() -> OIDCAuthHandler:
    """Get OIDC handler instance."""
    return OIDCAuthHandler()


def get_token_issuer(db: DbSession) -> TokenIssuer:
    """Get token issuer instance."""
    return TokenIssuer(db)


def get_rbac_engine(db: DbSession) -> RBACEngine:
    """Get RBAC engine instance."""
    return RBACEngine(db)


def get_user_service(db: DbSession) -> UserService:
    """Get user service instance."""
    return UserService(db)


def get_project_service(db: DbSession) -> ProjectService:
    """Get project service instance."""
    return ProjectService(db)


def get_membership_service(db: DbSession) -> MembershipService:
    """Get membership service instance."""
    return MembershipService(db)


def get_api_key_service(db: DbSession) -> APIKeyService:
    """Get API key service instance."""
    return APIKeyService(db)


def get_audit_service(db: DbSession) -> AuditService:
    """Get audit service instance."""
    return AuditService(db)


async def get_token_denylist() -> TokenDenylistService:
    """Get token denylist service."""
    redis = await get_redis()
    return TokenDenylistService(redis)


async def get_invitation_service() -> InvitationService:
    """Get invitation service."""
    redis = await get_redis()
    return InvitationService(redis)


async def get_brute_force_protection() -> BruteForceProtection:
    """Get brute force protection service."""
    redis = await get_redis()
    return BruteForceProtection(redis)


# Type aliases for dependencies
OIDCHandler = Annotated[OIDCAuthHandler, Depends(get_oidc_handler)]
TokenIssuerDep = Annotated[TokenIssuer, Depends(get_token_issuer)]
RBACEngineDep = Annotated[RBACEngine, Depends(get_rbac_engine)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
MembershipServiceDep = Annotated[MembershipService, Depends(get_membership_service)]
APIKeyServiceDep = Annotated[APIKeyService, Depends(get_api_key_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
TokenDenylistDep = Annotated[TokenDenylistService, Depends(get_token_denylist)]
InvitationServiceDep = Annotated[InvitationService, Depends(get_invitation_service)]
BruteForceDep = Annotated[BruteForceProtection, Depends(get_brute_force_protection)]


async def get_current_user(
    request: Request,
    db: DbSession,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    token_denylist: TokenDenylistService = Depends(get_token_denylist),
) -> User:
    """
    Validate JWT and return the current authenticated user.

    Raises:
        HTTPException: 401 if authentication fails.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check denylist
    jti = payload.get("jti")
    if jti:
        try:
            is_revoked = await token_denylist.is_token_revoked(jti)
            if is_revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception:
            # Fail closed if Redis is unavailable
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Token validation service unavailable",
            )

    # Get user from database
    user_id = UUID(payload["sub"])
    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    request: Request,
    db: DbSession,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    token_denylist: TokenDenylistService = Depends(get_token_denylist),
) -> Optional[User]:
    """
    Optional authentication - returns None if no valid token.
    """
    if not credentials:
        return None

    try:
        return await get_current_user(request, db, credentials, token_denylist)
    except HTTPException:
        return None


# Type aliases for authenticated user
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[Optional[User], Depends(get_current_user_optional)]


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_user_agent(
    user_agent: Optional[str] = Header(None, alias="User-Agent"),
) -> Optional[str]:
    """Extract user agent from request headers."""
    return user_agent


ClientIP = Annotated[Optional[str], Depends(get_client_ip)]
UserAgent = Annotated[Optional[str], Depends(get_user_agent)]
