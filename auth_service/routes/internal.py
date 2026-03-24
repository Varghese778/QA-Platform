"""Internal authorization endpoints for service-to-service calls."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from auth_service.dependencies import (
    DbSession,
    RBACEngineDep,
    MembershipServiceDep,
    AuditServiceDep,
    ClientIP,
)
from auth_service.models.enums import AuthzDecision
from auth_service.schemas import (
    AuthzRequest,
    AuthzResponse,
    MembershipQueryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/v1", tags=["internal"])


@router.post("/authz", response_model=AuthzResponse)
async def check_authorization(
    request: AuthzRequest,
    db: DbSession,
    rbac_engine: RBACEngineDep,
    audit_service: AuditServiceDep,
    client_ip: ClientIP,
) -> AuthzResponse:
    """
    Internal authorization endpoint for service-to-service calls.

    Called by other services to check if a user can perform an action.
    This endpoint should only be accessible from internal network.
    """
    decision, reason = await rbac_engine.check_permission(
        caller_id=request.caller_id,
        project_id=request.project_id,
        action=request.action,
        resource_type=request.resource_type,
    )

    # Log denials for audit
    if decision == AuthzDecision.DENY:
        await audit_service.log_authz_deny(
            user_id=request.caller_id,
            project_id=request.project_id,
            action=request.action,
            resource_type=request.resource_type,
            reason=reason or "Permission denied",
            ip_address=client_ip,
        )

    return AuthzResponse(
        decision=decision,
        reason=reason,
    )


@router.get(
    "/projects/{project_id}/membership", response_model=MembershipQueryResponse
)
async def query_membership(
    project_id: UUID,
    db: DbSession,
    membership_service: MembershipServiceDep,
    user_id: UUID = Query(..., description="User ID to check membership for"),
) -> MembershipQueryResponse:
    """
    Query a user's membership in a project.

    Called by other services to verify project membership.
    This endpoint should only be accessible from internal network.
    """
    is_member, role = await membership_service.check_membership(user_id, project_id)

    # Convert role string to enum if present
    from auth_service.models.enums import ProjectRole

    role_enum = None
    if role:
        try:
            role_enum = ProjectRole(role)
        except ValueError:
            pass

    return MembershipQueryResponse(
        is_member=is_member,
        role=role_enum,
    )
