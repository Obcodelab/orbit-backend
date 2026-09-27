from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from core.types import SortOrder
from modules.tasks.models import Task, TaskAssignee
from modules.tasks.types import TaskPriority, TaskSortField, TaskStatus

_SORT_COLUMNS = {
    TaskSortField.CREATED_AT: (Task.created_at, SortOrder.DESC),
    TaskSortField.DUE_DATE: (Task.due_date, SortOrder.ASC),
}


class TaskRepository(BaseRepository[Task]):
    model = Task

    async def create_task(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        project_id: UUID,
        number: int,
        parent_task_id: UUID | None,
        title: str,
        description: str | None,
        priority: TaskPriority,
        labels: str | None,
        due_date: date | None,
        created_by: UUID,
    ) -> Task:
        return await self.create(
            session,
            org_id=org_id,
            project_id=project_id,
            number=number,
            parent_task_id=parent_task_id,
            title=title,
            description=description,
            priority=priority,
            labels=labels,
            due_date=due_date,
            created_by=created_by,
        )

    async def get_scoped(
        self, session: AsyncSession, *, project_id: UUID, task_id: UUID
    ) -> Task | None:
        return await self.get_by(session, id=task_id, project_id=project_id)

    async def get_scoped_with_assignees(
        self, session: AsyncSession, *, project_id: UUID, task_id: UUID
    ) -> Task | None:
        stmt = (
            select(self.model)
            .where(self.model.id == task_id, self.model.project_id == project_id)
            .options(
                selectinload(self.model.assignees).selectinload(TaskAssignee.user),
                selectinload(self.model.project),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_fields(
        self, session: AsyncSession, *, task: Task, updates: dict
    ) -> Task:
        for field, value in updates.items():
            setattr(task, field, value)
        return await self.flush_and_refresh(session, task)

    async def get_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        status_filter: TaskStatus | None,
        priority_filter: TaskPriority | None,
        assignee_id: UUID | None,
        label: str | None,
        parent_id: UUID | None,
        sort: TaskSortField | None,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        stmt = select(self.model).where(self.model.project_id == project_id)
        if status_filter:
            stmt = stmt.where(self.model.status == status_filter)
        if priority_filter:
            stmt = stmt.where(self.model.priority == priority_filter)
        if assignee_id:
            stmt = stmt.join(TaskAssignee, TaskAssignee.task_id == self.model.id).where(
                TaskAssignee.user_id == assignee_id
            )
        if label:
            stmt = stmt.where(self.model.labels.ilike(f"%{label}%"))
        if parent_id:
            stmt = stmt.where(self.model.parent_task_id == parent_id)

        total = await self._count(session, stmt)
        stmt = self._apply_sort(
            stmt,
            sort=sort,
            order=order,
            columns=_SORT_COLUMNS,
            default_sort=TaskSortField.CREATED_AT,
        )

        stmt = (
            stmt.options(
                selectinload(self.model.assignees).selectinload(TaskAssignee.user),
                selectinload(self.model.project),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    async def count_by_status(
        self, session: AsyncSession, *, project_id: UUID
    ) -> dict[TaskStatus, int]:
        stmt = (
            select(self.model.status, func.count())
            .where(self.model.project_id == project_id)
            .group_by(self.model.status)
        )
        result = await session.execute(stmt)
        return dict(result.all())


task_repository = TaskRepository()
