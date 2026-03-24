"""Enum definitions for Auth & Access Control models."""

import enum


class UserStatus(str, enum.Enum):
    """User account status."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class ProjectStatus(str, enum.Enum):
    """Project status."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class Role(str, enum.Enum):
    """User roles for RBAC."""

    ORG_ADMIN = "ORG_ADMIN"
    PROJECT_ADMIN = "PROJECT_ADMIN"
    QA_ENGINEER = "QA_ENGINEER"
    VIEWER = "VIEWER"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"


class ProjectRole(str, enum.Enum):
    """Project-level roles (subset of Role for membership)."""

    PROJECT_ADMIN = "PROJECT_ADMIN"
    QA_ENGINEER = "QA_ENGINEER"
    VIEWER = "VIEWER"


class AuditEventType(str, enum.Enum):
    """Types of audit events."""

    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    TOKEN_ISSUED = "TOKEN_ISSUED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    ROLE_CHANGED = "ROLE_CHANGED"
    API_KEY_CREATED = "API_KEY_CREATED"
    API_KEY_REVOKED = "API_KEY_REVOKED"
    AUTHZ_DENY = "AUTHZ_DENY"


class AuditTargetType(str, enum.Enum):
    """Types of audit event targets."""

    USER = "USER"
    PROJECT = "PROJECT"
    MEMBERSHIP = "MEMBERSHIP"
    API_KEY = "API_KEY"


class AuditResult(str, enum.Enum):
    """Result of an audited operation."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class AuthzDecision(str, enum.Enum):
    """Authorization decision result."""

    ALLOW = "ALLOW"
    DENY = "DENY"


class TokenTypeHint(str, enum.Enum):
    """Token type hint for revocation."""

    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"


class GrantType(str, enum.Enum):
    """Supported grant types for token endpoint."""

    OIDC_EXCHANGE = "oidc_exchange"
    REFRESH_TOKEN = "refresh_token"
    API_KEY = "api_key"
