from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import BaseModel
from modules.organizations.types import OrganizationRole

if TYPE_CHECKING:
    from modules.auth.models import User

    from .organization import Organization


class OrganizationInvite(BaseModel):
    """Existence of a row means pending — accepting creates the matching
    OrganizationMember and deletes this row; declining just deletes it.
    Keyed by email, not user_id — the invitee doesn't need an account yet;
    they register with this email and the invite is simply there once
    they're a real logged-in user with a matching address."""

    __tablename__ = "organization_invites"

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[OrganizationRole] = mapped_column(String(20), nullable=False)
    invited_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    organization: Mapped[Organization] = relationship("Organization")
    inviter: Mapped[User | None] = relationship("User", foreign_keys=[invited_by])

    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_organization_invite"),
    )
