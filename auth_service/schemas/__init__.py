"""Schemas package - exports all Pydantic schemas."""

from auth_service.schemas.common import BaseSchema, ErrorResponse, HealthResponse
from auth_service.schemas.auth import (
    TokenRequest,
    TokenResponse,
    RevokeRequest,
    RevokeResponse,
    LogoutResponse,
    JWK,
    JWKSResponse,
    JWTClaims,
)
from auth_service.schemas.user import (
    UserProfile,
    UserResponse,
    APIKeyCreate,
    APIKeyRecord,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyRevokeResponse,
)
from auth_service.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectCreateResponse,
    ProjectListResponse,
    ProjectDeleteResponse,
    MemberRecord,
    MemberListResponse,
    MemberAdd,
    MemberAddResponse,
    MemberUpdate,
    MemberUpdateResponse,
    MemberRemoveResponse,
    InvitationCreate,
    InvitationResponse,
    InvitationAcceptResponse,
)
from auth_service.schemas.internal import (
    AuthzRequest,
    AuthzResponse,
    MembershipQueryResponse,
)

__all__ = [
    # Common
    "BaseSchema",
    "ErrorResponse",
    "HealthResponse",
    # Auth
    "TokenRequest",
    "TokenResponse",
    "RevokeRequest",
    "RevokeResponse",
    "LogoutResponse",
    "JWK",
    "JWKSResponse",
    "JWTClaims",
    # User
    "UserProfile",
    "UserResponse",
    "APIKeyCreate",
    "APIKeyRecord",
    "APIKeyCreateResponse",
    "APIKeyListResponse",
    "APIKeyRevokeResponse",
    # Project
    "ProjectCreate",
    "ProjectResponse",
    "ProjectCreateResponse",
    "ProjectListResponse",
    "ProjectDeleteResponse",
    "MemberRecord",
    "MemberListResponse",
    "MemberAdd",
    "MemberAddResponse",
    "MemberUpdate",
    "MemberUpdateResponse",
    "MemberRemoveResponse",
    "InvitationCreate",
    "InvitationResponse",
    "InvitationAcceptResponse",
    # Internal
    "AuthzRequest",
    "AuthzResponse",
    "MembershipQueryResponse",
]
