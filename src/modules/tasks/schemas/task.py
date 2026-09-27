from datetime import date, datetime

from pydantic import UUID7, BaseModel, Field

from core.schemas import FROM_ORM
from modules.organizations.schemas import MemberUserSummary
from modules.tasks.types import TaskPriority, TaskStatus


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    assignee_ids: list[UUID7] = Field(default_factory=list)
    parent_task_id: UUID7 | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    labels: str | None = None
    due_date: date | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    assignee_ids: list[UUID7] | None = None
    parent_task_id: UUID7 | None = None
    priority: TaskPriority | None = None
    labels: str | None = None
    due_date: date | None = None


class TaskStatusUpdateRequest(BaseModel):
    status: TaskStatus


class TaskResponse(BaseModel):
    model_config = FROM_ORM

    task_id: UUID7 = Field(validation_alias="id")
    key: str
    parent_task_id: UUID7 | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    labels: str | None
    due_date: date | None
    resolved_at: datetime | None
    created_by: UUID7
    assignees: list[MemberUserSummary]
