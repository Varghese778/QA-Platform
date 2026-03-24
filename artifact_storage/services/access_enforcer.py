"""Access Enforcer - project-level access control."""

import logging
from uuid import UUID

from artifact_storage.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AccessEnforcer:
    """Enforces project-level access isolation."""

    @staticmethod
    def check_project_access(project_id: UUID) -> None:
        """
        Verify project access is allowed.

        Args:
            project_id: Project to access

        Raises:
            PermissionError: If access is denied
        """
        # In production, this would check JWT claims and RBAC
        # For now, just validate the project_id is a valid UUID
        if not project_id:
            raise PermissionError("Project ID required")

        logger.debug(f"Access check passed for project {project_id}")

    @staticmethod
    def check_service_access(caller_service: str) -> None:
        """
        Verify service is allowed to call this module.

        Args:
            caller_service: Name of calling service

        Raises:
            PermissionError: If service is not in allowlist
        """
        if caller_service not in settings.allowed_services:
            logger.warning(f"Access denied for unauthorized service: {caller_service}")
            raise PermissionError(f"Service '{caller_service}' not allowed")

        logger.debug(f"Access check passed for service {caller_service}")


async def check_cross_project_access(
    artifact_project_id: UUID,
    request_project_id: UUID,
) -> None:
    """
    Verify no cross-project access.

    Args:
        artifact_project_id: Project that owns the artifact
        request_project_id: Project making the request

    Raises:
        PermissionError: If projects don't match
    """
    if artifact_project_id != request_project_id:
        logger.warning(
            f"Cross-project access attempt: {request_project_id} "
            f"accessing {artifact_project_id}"
        )
        raise PermissionError("Cross-project access denied")
