from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import BaseModel
from modules.projects.types import ProjectRole, ProjectStatus

if TYPE_CHECKING:
    from modules.auth.models import User
    from modules.organizations.models import Organization


class Project(BaseModel):
    __tablename__ = "projects"

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        String(20), nullable=False, default=ProjectStatus.ACTIVE
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    organization: Mapped[Organization] = relationship("Organization")
    members: Mapped[list[ProjectMember]] = relationship(
        "ProjectMember", back_populates="project"
    )

    __table_args__ = (UniqueConstraint("org_id", "key", name="uq_project_org_key"),)


class ProjectMember(BaseModel):
    __tablename__ = "project_members"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[ProjectRole] = mapped_column(String(20), nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="members")
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
