"""RBAC Engine - enforces role-based access control policies."""

import logging
from typing import Optional, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import Membership, User
from auth_service.models.enums import AuthzDecision, ProjectRole, Role

logger = logging.getLogger(__name__)


# RBAC Policy Matrix
# Maps (action, resource_type) -> set of roles that can perform the action
RBAC_POLICY: dict[tuple[str, str], Set[str]] = {
    # View jobs and reports - all roles
    ("view", "job"): {
        Role.VIEWER.value,
        Role.QA_ENGINEER.value,
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    ("view", "report"): {
        Role.VIEWER.value,
        Role.QA_ENGINEER.value,
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Submit jobs - QA_ENGINEER and above
    ("submit", "job"): {
        Role.QA_ENGINEER.value,
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Cancel own jobs - QA_ENGINEER and above
    ("cancel_own", "job"): {
        Role.QA_ENGINEER.value,
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Cancel any job - PROJECT_ADMIN and above
    ("cancel_any", "job"): {
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Export reports - QA_ENGINEER and above
    ("export", "report"): {
        Role.QA_ENGINEER.value,
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Manage project members - PROJECT_ADMIN and above
    ("manage", "member"): {
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    ("add", "member"): {
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    ("remove", "member"): {
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    ("update", "member"): {
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Delete project - ORG_ADMIN only
    ("delete", "project"): {
        Role.ORG_ADMIN.value,
    },
    # Create API keys - QA_ENGINEER and above (own keys only enforced separately)
    ("create", "api_key"): {
        Role.QA_ENGINEER.value,
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # View project settings
    ("view", "project"): {
        Role.VIEWER.value,
        Role.QA_ENGINEER.value,
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Update project settings - PROJECT_ADMIN and above
    ("update", "project"): {
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
    # Create project - ORG_ADMIN only
    ("create", "project"): {
        Role.ORG_ADMIN.value,
    },
    # Invite members
    ("invite", "member"): {
        Role.PROJECT_ADMIN.value,
        Role.ORG_ADMIN.value,
    },
}


class RBACEngine:
    """
    Evaluates authorization decisions against the RBAC policy matrix.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_role_in_project(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> Optional[str]:
        """
        Get a user's role in a specific project.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.

        Returns:
            Role name string or None if not a member.
        """
        stmt = select(Membership).where(
            Membership.user_id == user_id,
            Membership.project_id == project_id,
            Membership.removed_at.is_(None),
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership:
            return membership.role.value
        return None

    async def is_org_admin(self, user_id: UUID, org_id: UUID) -> bool:
        """
        Check if a user is an ORG_ADMIN for an organization.

        For MVP, we check if user has ORG_ADMIN role in any project of the org.
        In production, this would be a separate org-level membership table.

        Args:
            user_id: The user's UUID.
            org_id: The organization's UUID.

        Returns:
            True if user is an org admin.
        """
        # MVP: Check if user has created projects in this org or has admin access
        # This is simplified - in production, org membership would be separate
        from auth_service.models import Project

        stmt = (
            select(Membership)
            .join(Project, Membership.project_id == Project.project_id)
            .where(
                Membership.user_id == user_id,
                Project.org_id == org_id,
                Membership.role == ProjectRole.PROJECT_ADMIN,
                Membership.removed_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        # For MVP, if user is PROJECT_ADMIN in any project of the org,
        # treat as having elevated permissions
        return membership is not None

    async def check_permission(
        self,
        caller_id: UUID,
        project_id: UUID,
        action: str,
        resource_type: str,
    ) -> tuple[AuthzDecision, Optional[str]]:
        """
        Check if a caller has permission to perform an action.

        Args:
            caller_id: The user's UUID.
            project_id: The project context.
            action: The action to perform (e.g., "submit", "cancel_own").
            resource_type: The resource type (e.g., "job", "report").

        Returns:
            Tuple of (AuthzDecision, reason).
        """
        # Get user's role in the project
        role = await self.get_user_role_in_project(caller_id, project_id)

        if role is None:
            return AuthzDecision.DENY, "User is not a member of this project"

        # Look up policy
        policy_key = (action, resource_type)
        allowed_roles = RBAC_POLICY.get(policy_key)

        if allowed_roles is None:
            # Unknown action/resource - deny by default
            logger.warning(f"Unknown policy key: {policy_key}")
            return AuthzDecision.DENY, f"Unknown action/resource combination: {action}/{resource_type}"

        if role in allowed_roles:
            return AuthzDecision.ALLOW, None

        return (
            AuthzDecision.DENY,
            f"Role '{role}' does not have permission to {action} {resource_type}",
        )

    async def check_membership(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a user is a member of a project.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.

        Returns:
            Tuple of (is_member, role).
        """
        role = await self.get_user_role_in_project(user_id, project_id)
        return role is not None, role

    def can_role_perform_action(
        self,
        role: str,
        action: str,
        resource_type: str,
    ) -> bool:
        """
        Static check if a role can perform an action (no DB lookup).

        Args:
            role: The role name.
            action: The action to perform.
            resource_type: The resource type.

        Returns:
            True if the role has permission.
        """
        policy_key = (action, resource_type)
        allowed_roles = RBAC_POLICY.get(policy_key, set())
        return role in allowed_roles
