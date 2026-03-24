"""Project-related Pydantic schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from auth_service.models.enums import ProjectRole
from auth_service.schemas.common import BaseSchema


class ProjectCreate(BaseModel):
    """Project creation request schema."""

    name: str = Field(max_length=255)
    org_id: UUID
    description: Optional[str] = None


class ProjectResponse(BaseSchema):
    """Project response schema."""

    project_id: UUID
    name: str
    org_id: UUID
    description: Optional[str] = None
    member_count: int = 0
    created_at: datetime


class ProjectCreateResponse(BaseModel):
    """Project creation response schema."""

    project_id: UUID
    created_at: datetime


class ProjectListResponse(BaseModel):
    """List of projects response."""

    projects: List[ProjectResponse]


class ProjectDeleteResponse(BaseModel):
    """Project deletion response."""

    deleted: bool = True


class MemberRecord(BaseSchema):
    """Member record in a project."""

    membership_id: UUID
    user_id: UUID
    email: str
    name: str
    role: ProjectRole
    added_at: datetime


class MemberListResponse(BaseModel):
    """List of project members response."""

    members: List[MemberRecord]


class MemberAdd(BaseModel):
    """Add member to project request."""

    user_id: UUID
    role: ProjectRole


class MemberAddResponse(BaseModel):
    """Add member response."""

    membership_id: UUID
    user_id: UUID
    role: ProjectRole
    added_at: datetime


class MemberUpdate(BaseModel):
    """Update member role request."""

    role: ProjectRole


class MemberUpdateResponse(BaseModel):
    """Update member role response."""

    membership_id: UUID
    new_role: ProjectRole


class MemberRemoveResponse(BaseModel):
    """Remove member response."""

    removed: bool = True


class InvitationCreate(BaseModel):
    """Create invitation request."""

    email: EmailStr
    role: ProjectRole


class InvitationResponse(BaseModel):
    """Invitation creation response."""

    invitation_id: UUID
    invitation_token: str
    expires_at: datetime


class InvitationAcceptResponse(BaseModel):
    """Invitation acceptance response."""

    project_id: UUID
    role: ProjectRole
    membership_id: UUID
