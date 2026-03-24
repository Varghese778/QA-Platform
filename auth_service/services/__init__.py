"""Services package - exports all service classes."""

from auth_service.services.oidc_handler import (
    OIDCAuthHandler,
    OIDCUserClaims,
    OIDCValidationError,
)
from auth_service.services.token_issuer import TokenIssuer
from auth_service.services.rbac_engine import RBACEngine, RBAC_POLICY
from auth_service.services.redis_service import (
    get_redis,
    close_redis,
    TokenDenylistService,
    InvitationService,
    BruteForceProtection,
)
from auth_service.services.user_service import UserService
from auth_service.services.project_service import ProjectService
from auth_service.services.membership_service import MembershipService
from auth_service.services.api_key_service import APIKeyService
from auth_service.services.audit_service import AuditService

__all__ = [
    # OIDC
    "OIDCAuthHandler",
    "OIDCUserClaims",
    "OIDCValidationError",
    # Token
    "TokenIssuer",
    # RBAC
    "RBACEngine",
    "RBAC_POLICY",
    # Redis
    "get_redis",
    "close_redis",
    "TokenDenylistService",
    "InvitationService",
    "BruteForceProtection",
    # Stores
    "UserService",
    "ProjectService",
    "MembershipService",
    "APIKeyService",
    "AuditService",
]
