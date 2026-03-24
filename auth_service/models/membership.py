"""Membership model definition."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Enum as SQLEnum, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth_service.database import Base
from auth_service.models.enums import ProjectRole

if TYPE_CHECKING:
    from auth_service.models.user import User
    from auth_service.models.project import Project


class Membership(Base):
    """Membership entity representing user's role in a project."""

    __tablename__ = "memberships"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[ProjectRole] = mapped_column(
        SQLEnum(ProjectRole),
        nullable=False,
    )
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to User who added this member",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    removed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft remove timestamp; null if active",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="memberships",
    )
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="memberships",
    )
    added_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[added_by],
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_membership_project_user",
        ),
    )

    def __repr__(self) -> str:
        return f"<Membership(membership_id={self.membership_id}, role={self.role})>"
