"""Project and membership management routes."""

import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from auth_service.dependencies import (
    DbSession,
    ProjectServiceDep,
    MembershipServiceDep,
    UserServiceDep,
    RBACEngineDep,
    AuditServiceDep,
    InvitationServiceDep,
    CurrentUser,
    ClientIP,
)
from auth_service.models.enums import ProjectRole, AuthzDecision
from auth_service.schemas import (
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/v1", tags=["projects"])


@router.post("/projects", response_model=ProjectCreateResponse)
async def create_project(
    request: ProjectCreate,
    db: DbSession,
    project_service: ProjectServiceDep,
    membership_service: MembershipServiceDep,
    rbac_engine: RBACEngineDep,
    current_user: CurrentUser,
) -> ProjectCreateResponse:
    """
    Create a new project.

    The creating user becomes PROJECT_ADMIN automatically.
    """
    # For MVP, any authenticated user can create projects
    # In production, would check ORG_ADMIN permission

    project = await project_service.create_project(
        name=request.name,
        org_id=request.org_id,
        description=request.description,
    )

    # Add creator as PROJECT_ADMIN
    await membership_service.add_member(
        project_id=project.project_id,
        user_id=current_user.user_id,
        role=ProjectRole.PROJECT_ADMIN,
    )

    return ProjectCreateResponse(
        project_id=project.project_id,
        created_at=project.created_at,
    )


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    db: DbSession,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectListResponse:
    """
    List all projects the current user is a member of.
    """
    projects = await project_service.get_user_projects(current_user.user_id)

    project_responses = []
    for project in projects:
        member_count = await project_service.get_member_count(project.project_id)
        project_responses.append(
            ProjectResponse(
                project_id=project.project_id,
                name=project.name,
                org_id=project.org_id,
                description=project.description,
                member_count=member_count,
                created_at=project.created_at,
            )
        )

    return ProjectListResponse(projects=project_responses)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: DbSession,
    project_service: ProjectServiceDep,
    membership_service: MembershipServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    """
    Get project details.

    User must be a member of the project.
    """
    # Check membership
    membership = await membership_service.get_membership(
        project_id, current_user.user_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this project",
        )

    project = await project_service.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    member_count = await project_service.get_member_count(project_id)

    return ProjectResponse(
        project_id=project.project_id,
        name=project.name,
        org_id=project.org_id,
        description=project.description,
        member_count=member_count,
        created_at=project.created_at,
    )


@router.delete("/projects/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(
    project_id: UUID,
    db: DbSession,
    project_service: ProjectServiceDep,
    rbac_engine: RBACEngineDep,
    current_user: CurrentUser,
) -> ProjectDeleteResponse:
    """
    Delete a project (soft delete).

    Requires ORG_ADMIN permission.
    """
    # Check permission
    decision, reason = await rbac_engine.check_permission(
        caller_id=current_user.user_id,
        project_id=project_id,
        action="delete",
        resource_type="project",
    )

    if decision == AuthzDecision.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Permission denied",
        )

    deleted = await project_service.delete_project(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return ProjectDeleteResponse(deleted=True)


@router.get("/projects/{project_id}/members", response_model=MemberListResponse)
async def list_members(
    project_id: UUID,
    db: DbSession,
    membership_service: MembershipServiceDep,
    current_user: CurrentUser,
) -> MemberListResponse:
    """
    List all members of a project.

    User must be a member of the project.
    """
    # Check membership
    membership = await membership_service.get_membership(
        project_id, current_user.user_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this project",
        )

    members = await membership_service.get_project_members(project_id)

    return MemberListResponse(
        members=[
            MemberRecord(
                membership_id=m.membership_id,
                user_id=m.user_id,
                email=u.email,
                name=u.name,
                role=m.role,
                added_at=m.added_at,
            )
            for m, u in members
        ]
    )


@router.post("/projects/{project_id}/members", response_model=MemberAddResponse)
async def add_member(
    project_id: UUID,
    request: MemberAdd,
    db: DbSession,
    membership_service: MembershipServiceDep,
    user_service: UserServiceDep,
    rbac_engine: RBACEngineDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
) -> MemberAddResponse:
    """
    Add a user to a project.

    Requires PROJECT_ADMIN or ORG_ADMIN permission.
    """
    # Check permission
    decision, reason = await rbac_engine.check_permission(
        caller_id=current_user.user_id,
        project_id=project_id,
        action="add",
        resource_type="member",
    )

    if decision == AuthzDecision.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Permission denied",
        )

    # Check if user exists
    user = await user_service.get_by_id(request.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already a member
    existing = await membership_service.get_membership(project_id, request.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this project",
        )

    membership = await membership_service.add_member(
        project_id=project_id,
        user_id=request.user_id,
        role=request.role,
        added_by=current_user.user_id,
    )

    await audit_service.log_member_added(
        actor_id=current_user.user_id,
        target_user_id=request.user_id,
        project_id=project_id,
        ip_address=client_ip,
    )

    return MemberAddResponse(
        membership_id=membership.membership_id,
        user_id=membership.user_id,
        role=membership.role,
        added_at=membership.added_at,
    )


@router.put(
    "/projects/{project_id}/members/{user_id}", response_model=MemberUpdateResponse
)
async def update_member_role(
    project_id: UUID,
    user_id: UUID,
    request: MemberUpdate,
    db: DbSession,
    membership_service: MembershipServiceDep,
    rbac_engine: RBACEngineDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
) -> MemberUpdateResponse:
    """
    Update a member's role in a project.

    Requires PROJECT_ADMIN or ORG_ADMIN permission.
    """
    # Check permission
    decision, reason = await rbac_engine.check_permission(
        caller_id=current_user.user_id,
        project_id=project_id,
        action="update",
        resource_type="member",
    )

    if decision == AuthzDecision.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Permission denied",
        )

    membership = await membership_service.update_role(project_id, user_id, request.role)

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    await audit_service.log_role_changed(
        actor_id=current_user.user_id,
        target_user_id=user_id,
        project_id=project_id,
        ip_address=client_ip,
    )

    return MemberUpdateResponse(
        membership_id=membership.membership_id,
        new_role=membership.role,
    )


@router.delete(
    "/projects/{project_id}/members/{user_id}", response_model=MemberRemoveResponse
)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    db: DbSession,
    membership_service: MembershipServiceDep,
    rbac_engine: RBACEngineDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
) -> MemberRemoveResponse:
    """
    Remove a member from a project.

    Requires PROJECT_ADMIN or ORG_ADMIN permission.
    Cannot remove the last PROJECT_ADMIN.
    """
    # Check permission
    decision, reason = await rbac_engine.check_permission(
        caller_id=current_user.user_id,
        project_id=project_id,
        action="remove",
        resource_type="member",
    )

    if decision == AuthzDecision.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Permission denied",
        )

    # Check if removing last admin
    if await membership_service.is_last_admin(project_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove the last PROJECT_ADMIN. Assign a new admin first.",
        )

    removed = await membership_service.remove_member(project_id, user_id)

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    await audit_service.log_member_removed(
        actor_id=current_user.user_id,
        target_user_id=user_id,
        project_id=project_id,
        ip_address=client_ip,
    )

    return MemberRemoveResponse(removed=True)


@router.post(
    "/projects/{project_id}/invitations", response_model=InvitationResponse
)
async def create_invitation(
    project_id: UUID,
    request: InvitationCreate,
    db: DbSession,
    rbac_engine: RBACEngineDep,
    invitation_service: InvitationServiceDep,
    current_user: CurrentUser,
) -> InvitationResponse:
    """
    Create a project invitation.

    Requires PROJECT_ADMIN or ORG_ADMIN permission.
    """
    # Check permission
    decision, reason = await rbac_engine.check_permission(
        caller_id=current_user.user_id,
        project_id=project_id,
        action="invite",
        resource_type="member",
    )

    if decision == AuthzDecision.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Permission denied",
        )

    invitation_id = uuid.uuid4()
    invitation_token = uuid.uuid4().hex

    expires_at = await invitation_service.create_invitation(
        invitation_id=invitation_id,
        invitation_token=invitation_token,
        project_id=project_id,
        email=request.email,
        role=request.role.value,
        invited_by=current_user.user_id,
    )

    return InvitationResponse(
        invitation_id=invitation_id,
        invitation_token=invitation_token,
        expires_at=expires_at,
    )


# Invitations router (separate prefix)
invitations_router = APIRouter(prefix="/auth/v1/invitations", tags=["invitations"])


@invitations_router.post(
    "/{invitation_token}/accept", response_model=InvitationAcceptResponse
)
async def accept_invitation(
    invitation_token: str,
    db: DbSession,
    invitation_service: InvitationServiceDep,
    membership_service: MembershipServiceDep,
    audit_service: AuditServiceDep,
    current_user: CurrentUser,
    client_ip: ClientIP,
) -> InvitationAcceptResponse:
    """
    Accept a project invitation.
    """
    invitation = await invitation_service.consume_invitation(invitation_token)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation not found or expired",
        )

    project_id = UUID(invitation["project_id"])
    role = ProjectRole(invitation["role"])

    # Check if already a member
    existing = await membership_service.get_membership(project_id, current_user.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already a member of this project",
        )

    membership = await membership_service.add_member(
        project_id=project_id,
        user_id=current_user.user_id,
        role=role,
        added_by=UUID(invitation["invited_by"]),
    )

    await audit_service.log_member_added(
        actor_id=UUID(invitation["invited_by"]),
        target_user_id=current_user.user_id,
        project_id=project_id,
        ip_address=client_ip,
    )

    return InvitationAcceptResponse(
        project_id=project_id,
        role=role,
        membership_id=membership.membership_id,
    )
