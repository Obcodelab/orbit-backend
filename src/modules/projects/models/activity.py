from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import BaseModel
from modules.projects.types import ActivityAction

if TYPE_CHECKING:
    from modules.auth.models import User


class ActivityLogEntry(BaseModel):
    __tablename__ = "activity_log_entries"

    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[ActivityAction] = mapped_column(String(100), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)

    actor: Mapped[User] = relationship("User", foreign_keys=[actor_id])
