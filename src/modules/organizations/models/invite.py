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
    """Existence of a row means pending — accept/decline both delete it.
    Keyed by email, not user_id, since the invitee doesn't need an
    account yet."""

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
