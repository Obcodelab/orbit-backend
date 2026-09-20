from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import BaseModel
from modules.organizations.types import OrganizationRole

if TYPE_CHECKING:
    from modules.auth.models import User


class Organization(BaseModel):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    members: Mapped[list[OrganizationMember]] = relationship(
        "OrganizationMember", back_populates="organization"
    )


class OrganizationMember(BaseModel):
    __tablename__ = "organization_members"

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrganizationRole] = mapped_column(String(20), nullable=False)

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="members"
    )
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_organization_member"),
    )
