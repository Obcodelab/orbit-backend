from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import BaseModel
from modules.tasks.types import TaskPriority, TaskStatus

if TYPE_CHECKING:
    from modules.auth.models import User
    from modules.organizations.models import Organization
    from modules.projects.models import Project


class Task(BaseModel):
    __tablename__ = "tasks"

    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        String(20), nullable=False, default=TaskStatus.TODO
    )
    priority: Mapped[TaskPriority] = mapped_column(
        String(20), nullable=False, default=TaskPriority.MEDIUM
    )
    labels: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship("Organization")
    project: Mapped[Project] = relationship("Project")
    assignees: Mapped[list[TaskAssignee]] = relationship(
        "TaskAssignee", back_populates="task"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "number", name="uq_task_project_number"),
    )


class TaskAssignee(BaseModel):
    __tablename__ = "task_assignees"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    task: Mapped[Task] = relationship("Task", back_populates="assignees")
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])

    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_assignee"),)


class Comment(BaseModel):
    __tablename__ = "comments"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
