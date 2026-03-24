"""Audit Logger - writes structured audit events."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import AuditEvent
from auth_service.models.enums import AuditEventType, AuditTargetType, AuditResult

logger = logging.getLogger(__name__)


class AuditService:
    """
    Writes structured audit events for authentication and authorization decisions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        event_type: AuditEventType,
        result: AuditResult,
        actor_id: Optional[UUID] = None,
        target_id: Optional[UUID] = None,
        target_type: Optional[AuditTargetType] = None,
        project_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of the event.
            result: SUCCESS or FAILURE.
            actor_id: User performing the action.
            target_id: Resource affected.
            target_type: Type of the target resource.
            project_id: Project context.
            ip_address: Source IP.
            user_agent: Client user agent.
            failure_reason: Reason for failure (if applicable).

        Returns:
            Created AuditEvent entity.
        """
        audit_event = AuditEvent(
            event_type=event_type,
            actor_id=actor_id,
            target_id=target_id,
            target_type=target_type,
            project_id=project_id,
            ip_address=ip_address,
            user_agent=user_agent,
            result=result,
            failure_reason=failure_reason,
        )
        self.db.add(audit_event)
        await self.db.flush()

        log_level = logging.INFO if result == AuditResult.SUCCESS else logging.WARNING
        logger.log(
            log_level,
            f"Audit: {event_type.value} - {result.value} - "
            f"actor={actor_id}, target={target_id}",
        )

        return audit_event

    async def log_login(
        self,
        user_id: UUID,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> AuditEvent:
        """Log a login attempt."""
        return await self.log_event(
            event_type=AuditEventType.LOGIN,
            result=AuditResult.SUCCESS if success else AuditResult.FAILURE,
            actor_id=user_id,
            target_id=user_id,
            target_type=AuditTargetType.USER,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )

    async def log_logout(
        self,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        """Log a logout event."""
        return await self.log_event(
            event_type=AuditEventType.LOGOUT,
            result=AuditResult.SUCCESS,
            actor_id=user_id,
            target_id=user_id,
            target_type=AuditTargetType.USER,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_token_issued(
        self,
        user_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log a token issuance event."""
        return await self.log_event(
            event_type=AuditEventType.TOKEN_ISSUED,
            result=AuditResult.SUCCESS,
            actor_id=user_id,
            target_id=user_id,
            target_type=AuditTargetType.USER,
            ip_address=ip_address,
        )

    async def log_token_revoked(
        self,
        user_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log a token revocation event."""
        return await self.log_event(
            event_type=AuditEventType.TOKEN_REVOKED,
            result=AuditResult.SUCCESS,
            actor_id=user_id,
            target_id=user_id,
            target_type=AuditTargetType.USER,
            ip_address=ip_address,
        )

    async def log_member_added(
        self,
        actor_id: UUID,
        target_user_id: UUID,
        project_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log a member addition event."""
        return await self.log_event(
            event_type=AuditEventType.MEMBER_ADDED,
            result=AuditResult.SUCCESS,
            actor_id=actor_id,
            target_id=target_user_id,
            target_type=AuditTargetType.MEMBERSHIP,
            project_id=project_id,
            ip_address=ip_address,
        )

    async def log_member_removed(
        self,
        actor_id: UUID,
        target_user_id: UUID,
        project_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log a member removal event."""
        return await self.log_event(
            event_type=AuditEventType.MEMBER_REMOVED,
            result=AuditResult.SUCCESS,
            actor_id=actor_id,
            target_id=target_user_id,
            target_type=AuditTargetType.MEMBERSHIP,
            project_id=project_id,
            ip_address=ip_address,
        )

    async def log_role_changed(
        self,
        actor_id: UUID,
        target_user_id: UUID,
        project_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log a role change event."""
        return await self.log_event(
            event_type=AuditEventType.ROLE_CHANGED,
            result=AuditResult.SUCCESS,
            actor_id=actor_id,
            target_id=target_user_id,
            target_type=AuditTargetType.MEMBERSHIP,
            project_id=project_id,
            ip_address=ip_address,
        )

    async def log_api_key_created(
        self,
        user_id: UUID,
        api_key_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log an API key creation event."""
        return await self.log_event(
            event_type=AuditEventType.API_KEY_CREATED,
            result=AuditResult.SUCCESS,
            actor_id=user_id,
            target_id=api_key_id,
            target_type=AuditTargetType.API_KEY,
            ip_address=ip_address,
        )

    async def log_api_key_revoked(
        self,
        user_id: UUID,
        api_key_id: UUID,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log an API key revocation event."""
        return await self.log_event(
            event_type=AuditEventType.API_KEY_REVOKED,
            result=AuditResult.SUCCESS,
            actor_id=user_id,
            target_id=api_key_id,
            target_type=AuditTargetType.API_KEY,
            ip_address=ip_address,
        )

    async def log_authz_deny(
        self,
        user_id: UUID,
        project_id: UUID,
        action: str,
        resource_type: str,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Log an authorization denial event."""
        return await self.log_event(
            event_type=AuditEventType.AUTHZ_DENY,
            result=AuditResult.FAILURE,
            actor_id=user_id,
            project_id=project_id,
            failure_reason=f"{action}/{resource_type}: {reason}",
            ip_address=ip_address,
        )
