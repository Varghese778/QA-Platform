"""Internal authorization schemas."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from auth_service.models.enums import AuthzDecision, ProjectRole


class AuthzRequest(BaseModel):
    """Authorization check request."""

    caller_id: UUID
    project_id: UUID
    action: str = Field(description="Action to authorize (e.g., submit_job, cancel_job)")
    resource_type: str = Field(description="Resource type (e.g., job, report)")


class AuthzResponse(BaseModel):
    """Authorization check response."""

    decision: AuthzDecision
    reason: Optional[str] = None


class MembershipQueryResponse(BaseModel):
    """Membership query response for internal use."""

    role: Optional[ProjectRole] = None
    is_member: bool
