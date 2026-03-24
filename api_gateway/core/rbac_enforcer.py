"""RBAC Enforcer - Checks caller role against route permission matrix."""

import logging
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


# Route permission matrix: (method, path_pattern) -> set of allowed roles
# Roles: VIEWER, QA_ENGINEER, PROJECT_ADMIN, ORG_ADMIN
ROUTE_PERMISSIONS: Dict[tuple, Set[str]] = {
    # Jobs - require project membership with appropriate role
    ("POST", "/api/v1/jobs"): {"QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    ("GET", "/api/v1/jobs"): {"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    ("GET", "/api/v1/jobs/{job_id}"): {"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    ("DELETE", "/api/v1/jobs/{job_id}"): {"QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    ("GET", "/api/v1/jobs/{job_id}/tests"): {"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    ("GET", "/api/v1/jobs/{job_id}/report"): {"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    ("GET", "/api/v1/jobs/{job_id}/export"): {"QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    # Projects - any authenticated user can list their projects
    ("GET", "/api/v1/projects"): {"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    ("GET", "/api/v1/projects/{project_id}"): {"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    # Uploads - require at least QA_ENGINEER
    ("POST", "/api/v1/uploads"): {"QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
    # WebSocket
    ("GET", "/ws/v1/jobs/{job_id}/status"): {"VIEWER", "QA_ENGINEER", "PROJECT_ADMIN", "ORG_ADMIN"},
}

# Public routes that don't require authentication
PUBLIC_ROUTES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("OPTIONS", "*"),  # CORS preflight
}


class RBACEnforcer:
    """
    Enforces role-based access control based on JWT claims.

    Checks caller's project-specific roles against route permission matrix.
    """

    def __init__(self, permissions: Optional[Dict[tuple, Set[str]]] = None):
        """
        Initialize RBAC enforcer.

        Args:
            permissions: Custom permission matrix (uses default if not provided).
        """
        self.permissions = permissions or ROUTE_PERMISSIONS

    def is_public_route(self, method: str, path: str) -> bool:
        """Check if route is public (no auth required)."""
        if (method, path) in PUBLIC_ROUTES:
            return True
        if (method, "*") in PUBLIC_ROUTES:
            return True
        # Health endpoints
        if path.startswith("/health/"):
            return True
        return False

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path by replacing UUIDs with placeholders.

        E.g., /api/v1/jobs/123e4567-e89b-12d3-a456-426614174000
              becomes /api/v1/jobs/{job_id}
        """
        import re

        # UUID pattern
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

        # Replace UUIDs in path segments
        parts = path.split("/")
        normalized = []

        for i, part in enumerate(parts):
            if re.match(f"^{uuid_pattern}$", part, re.IGNORECASE):
                # Determine placeholder based on previous segment
                prev = parts[i - 1] if i > 0 else ""
                if prev == "jobs":
                    normalized.append("{job_id}")
                elif prev == "projects":
                    normalized.append("{project_id}")
                elif prev == "users":
                    normalized.append("{user_id}")
                else:
                    normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)

    def get_required_roles(self, method: str, path: str) -> Optional[Set[str]]:
        """
        Get roles required for a route.

        Returns:
            Set of allowed roles, or None if route not in matrix.
        """
        normalized = self._normalize_path(path)
        return self.permissions.get((method, normalized))

    def check_permission(
        self,
        method: str,
        path: str,
        roles: Dict[str, str],
        project_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if caller has permission to access a route.

        Args:
            method: HTTP method.
            path: Request path.
            roles: Dict mapping project_id -> role from JWT claims.
            project_id: Target project context.

        Returns:
            Tuple of (allowed: bool, reason: Optional[str]).
        """
        # Check if public route
        if self.is_public_route(method, path):
            return True, None

        # Get required roles for this route
        required_roles = self.get_required_roles(method, path)

        if required_roles is None:
            # Route not in explicit matrix - deny by default
            logger.warning(f"Route not in RBAC matrix: {method} {path}")
            return False, "Route not configured for access control"

        if not roles:
            return False, "No role claims in token"

        # For project-scoped routes, check project-specific role
        if project_id:
            user_role = roles.get(project_id)
            if not user_role:
                return False, f"Not a member of project {project_id}"

            if user_role in required_roles:
                return True, None

            return (
                False,
                f"Role '{user_role}' does not have permission for this operation",
            )

        # For non-project routes (like GET /projects), check if user has ANY valid role
        # This allows listing projects the user belongs to
        if any(role in required_roles for role in roles.values()):
            return True, None

        return False, "Insufficient permissions for this operation"

    def get_user_projects(self, roles: Dict[str, str]) -> list:
        """Get list of project IDs the user has access to."""
        return list(roles.keys())
