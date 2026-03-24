"""User-related Pydantic schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from auth_service.schemas.common import BaseSchema


class UserProfile(BaseSchema):
    """User profile response schema."""

    user_id: UUID
    email: EmailStr
    name: str
    orgs: List[UUID] = Field(default_factory=list)
    created_at: datetime


class UserResponse(BaseSchema):
    """User detail response schema."""

    user_id: UUID
    email: EmailStr
    name: str
    created_at: datetime


class APIKeyCreate(BaseModel):
    """API key creation request schema."""

    description: str = Field(max_length=255)
    expires_at: Optional[datetime] = Field(
        None,
        description="Optional expiry; null = no expiry",
    )


class APIKeyRecord(BaseSchema):
    """API key record (without raw key)."""

    api_key_id: UUID
    description: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class APIKeyCreateResponse(BaseModel):
    """API key creation response (includes raw key once)."""

    api_key_id: UUID
    key: str = Field(description="Raw API key value (shown once)")
    description: str
    expires_at: Optional[datetime] = None


class APIKeyListResponse(BaseModel):
    """List of API keys response."""

    api_keys: List[APIKeyRecord]


class APIKeyRevokeResponse(BaseModel):
    """API key revocation response."""

    revoked: bool = True
