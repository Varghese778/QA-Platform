"""Authentication routes - token endpoint, revoke, logout, JWKS."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from auth_service.dependencies import (
    DbSession,
    OIDCHandler,
    TokenIssuerDep,
    UserServiceDep,
    APIKeyServiceDep,
    AuditServiceDep,
    TokenDenylistDep,
    BruteForceDep,
    CurrentUser,
    ClientIP,
    UserAgent,
)
from auth_service.models.enums import GrantType
from auth_service.schemas import (
    TokenRequest,
    TokenResponse,
    RevokeRequest,
    RevokeResponse,
    LogoutResponse,
    JWKSResponse,
)
from auth_service.services import OIDCValidationError
from auth_service.utils import get_jwks, decode_access_token
from auth_service.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth/v1", tags=["authentication"])


@router.post("/token", response_model=TokenResponse)
async def token_endpoint(
    request: TokenRequest,
    http_request: Request,
    db: DbSession,
    oidc_handler: OIDCHandler,
    token_issuer: TokenIssuerDep,
    user_service: UserServiceDep,
    api_key_service: APIKeyServiceDep,
    audit_service: AuditServiceDep,
    brute_force: BruteForceDep,
    client_ip: ClientIP,
    user_agent: UserAgent,
) -> TokenResponse:
    """
    Token endpoint supporting multiple grant types.

    - **oidc_exchange**: Exchange IdP identity token for platform tokens
    - **refresh_token**: Refresh access token using refresh token
    - **api_key**: Authenticate using API key
    """
    if request.grant_type == GrantType.OIDC_EXCHANGE:
        return await _handle_oidc_exchange(
            request,
            oidc_handler,
            token_issuer,
            user_service,
            audit_service,
            brute_force,
            client_ip,
            user_agent,
        )
    elif request.grant_type == GrantType.REFRESH_TOKEN:
        return await _handle_refresh_token(
            request,
            token_issuer,
            audit_service,
            client_ip,
        )
    elif request.grant_type == GrantType.API_KEY:
        return await _handle_api_key(
            request,
            token_issuer,
            api_key_service,
            audit_service,
            client_ip,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant type: {request.grant_type}",
        )


async def _handle_oidc_exchange(
    request: TokenRequest,
    oidc_handler: OIDCHandler,
    token_issuer: TokenIssuerDep,
    user_service: UserServiceDep,
    audit_service: AuditServiceDep,
    brute_force: BruteForceDep,
    client_ip: ClientIP,
    user_agent: UserAgent,
) -> TokenResponse:
    """Handle OIDC token exchange grant type."""
    if not request.identity_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="identity_token is required for oidc_exchange grant",
        )

    try:
        # Validate IdP token
        claims = await oidc_handler.validate_identity_token(request.identity_token)
    except OIDCValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid identity token: {e.message}",
        )

    # Check brute force protection
    if await brute_force.is_locked(claims.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed attempts",
        )

    # Get or create user (auto-provision)
    user, was_created = await user_service.get_or_create_user(
        idp_subject=claims.sub,
        idp_provider=claims.idp_provider,
        email=claims.email,
        name=claims.name,
    )

    # Check user status
    if user.status.value != "ACTIVE":
        await brute_force.record_failed_attempt(claims.email)
        await audit_service.log_login(
            user_id=user.user_id,
            success=False,
            ip_address=client_ip,
            user_agent=user_agent,
            failure_reason=f"User status: {user.status.value}",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    # Update last login
    await user_service.update_last_login(user.user_id)

    # Issue tokens
    access_token, refresh_token, expires_in = await token_issuer.issue_tokens(user)

    # Clear brute force attempts on success
    await brute_force.clear_attempts(claims.email)

    # Log successful login
    await audit_service.log_login(
        user_id=user.user_id,
        success=True,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    await audit_service.log_token_issued(user_id=user.user_id, ip_address=client_ip)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


async def _handle_refresh_token(
    request: TokenRequest,
    token_issuer: TokenIssuerDep,
    audit_service: AuditServiceDep,
    client_ip: ClientIP,
) -> TokenResponse:
    """Handle refresh token grant type."""
    if not request.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required for refresh_token grant",
        )

    result = await token_issuer.refresh_tokens(request.refresh_token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    access_token, new_refresh_token, expires_in, user_id = result

    await audit_service.log_token_issued(user_id=user_id, ip_address=client_ip)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
    )


async def _handle_api_key(
    request: TokenRequest,
    token_issuer: TokenIssuerDep,
    api_key_service: APIKeyServiceDep,
    audit_service: AuditServiceDep,
    client_ip: ClientIP,
) -> TokenResponse:
    """Handle API key grant type."""
    if not request.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required for api_key grant",
        )

    user = await api_key_service.validate_api_key(request.api_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Issue access token only (no refresh token for API key auth)
    access_token, expires_in = await token_issuer.issue_access_token_only(user)

    await audit_service.log_token_issued(user_id=user.user_id, ip_address=client_ip)

    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=None,
    )


@router.post("/revoke", response_model=RevokeResponse)
async def revoke_token(
    request: RevokeRequest,
    db: DbSession,
    token_issuer: TokenIssuerDep,
    token_denylist: TokenDenylistDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
) -> RevokeResponse:
    """
    Revoke an access or refresh token.
    """
    # Try to revoke as refresh token first
    revoked = await token_issuer.revoke_refresh_token(request.token)

    if not revoked:
        # Try to decode as access token and add to denylist
        try:
            payload = decode_access_token(request.token)
            jti = payload.get("jti")
            exp = payload.get("exp")

            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                await token_denylist.add_to_denylist(jti, expires_at)
                revoked = True
        except Exception:
            # Token couldn't be decoded - may already be invalid
            pass

    await audit_service.log_token_revoked(
        user_id=current_user.user_id,
        ip_address=client_ip,
    )

    return RevokeResponse(revoked=True)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    db: DbSession,
    token_issuer: TokenIssuerDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
    user_agent: UserAgent,
) -> LogoutResponse:
    """
    Logout - revoke all refresh tokens for the current user.
    """
    await token_issuer.revoke_all_user_tokens(current_user.user_id)

    await audit_service.log_logout(
        user_id=current_user.user_id,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    return LogoutResponse(logged_out=True)


@router.get("/.well-known/jwks.json", response_model=JWKSResponse)
async def get_jwks_endpoint() -> JWKSResponse:
    """
    JWKS endpoint - serves public keys for JWT signature verification.

    This endpoint is consumed by the API Gateway for token validation.
    """
    jwks = get_jwks()
    return JWKSResponse(**jwks)
