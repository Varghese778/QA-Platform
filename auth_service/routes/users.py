"""User management routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from auth_service.dependencies import (
    DbSession,
    UserServiceDep,
    APIKeyServiceDep,
    AuditServiceDep,
    CurrentUser,
    ClientIP,
)
from auth_service.schemas import (
    UserProfile,
    UserResponse,
    APIKeyCreate,
    APIKeyRecord,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyRevokeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/v1/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    db: DbSession,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> UserProfile:
    """
    Get the current authenticated user's profile.
    """
    orgs = await user_service.get_user_organizations(current_user.user_id)

    return UserProfile(
        user_id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        orgs=orgs,
        created_at=current_user.created_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: DbSession,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """
    Get a user by ID.

    Users can only view their own profile unless they have elevated permissions.
    """
    # For MVP, allow users to see their own profile or any user (for membership lists)
    user = await user_service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
    )


@router.post("/{user_id}/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    user_id: UUID,
    request: APIKeyCreate,
    db: DbSession,
    api_key_service: APIKeyServiceDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
) -> APIKeyCreateResponse:
    """
    Create a new API key for a user.

    Users can only create API keys for themselves.
    """
    # Users can only create keys for themselves
    if current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create API keys for other users",
        )

    api_key, raw_key = await api_key_service.create_api_key(
        user_id=user_id,
        description=request.description,
        expires_at=request.expires_at,
    )

    await audit_service.log_api_key_created(
        user_id=current_user.user_id,
        api_key_id=api_key.api_key_id,
        ip_address=client_ip,
    )

    return APIKeyCreateResponse(
        api_key_id=api_key.api_key_id,
        key=raw_key,
        description=api_key.description,
        expires_at=api_key.expires_at,
    )


@router.get("/{user_id}/api-keys", response_model=APIKeyListResponse)
async def list_api_keys(
    user_id: UUID,
    db: DbSession,
    api_key_service: APIKeyServiceDep,
    current_user: CurrentUser,
) -> APIKeyListResponse:
    """
    List all API keys for a user.

    Users can only list their own API keys.
    """
    if current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view API keys for other users",
        )

    keys = await api_key_service.get_user_api_keys(user_id)

    return APIKeyListResponse(
        api_keys=[
            APIKeyRecord(
                api_key_id=key.api_key_id,
                description=key.description,
                created_at=key.created_at,
                expires_at=key.expires_at,
                last_used_at=key.last_used_at,
            )
            for key in keys
        ]
    )


@router.delete("/{user_id}/api-keys/{key_id}", response_model=APIKeyRevokeResponse)
async def revoke_api_key(
    user_id: UUID,
    key_id: UUID,
    db: DbSession,
    api_key_service: APIKeyServiceDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
) -> APIKeyRevokeResponse:
    """
    Revoke an API key.

    Users can only revoke their own API keys.
    """
    if current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot revoke API keys for other users",
        )

    revoked = await api_key_service.revoke_api_key(key_id, user_id)

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    await audit_service.log_api_key_revoked(
        user_id=current_user.user_id,
        api_key_id=key_id,
        ip_address=client_ip,
    )

    return APIKeyRevokeResponse(revoked=True)
