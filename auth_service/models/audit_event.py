"""AuditEvent model definition."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Enum as SQLEnum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from auth_service.database import Base
from auth_service.models.enums import AuditEventType, AuditTargetType, AuditResult


class AuditEvent(Base):
    """AuditEvent entity for tracking authentication and authorization events."""

    __tablename__ = "audit_events"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        SQLEnum(AuditEventType),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User or service account performing the action",
    )
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User, project, or resource affected",
    )
    target_type: Mapped[Optional[AuditTargetType]] = mapped_column(
        SQLEnum(AuditTargetType),
        nullable=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Project context; null for org-level events",
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Source IP address (supports IPv6)",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Client user agent",
    )
    result: Mapped[AuditResult] = mapped_column(
        SQLEnum(AuditResult),
        nullable=False,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Populated on FAILURE",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(audit_id={self.audit_id}, event_type={self.event_type})>"
