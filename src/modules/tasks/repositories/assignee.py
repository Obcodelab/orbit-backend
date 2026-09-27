from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from modules.projects.models import Project
from modules.tasks.models import Task, TaskAssignee


class TaskAssigneeRepository(BaseRepository[TaskAssignee]):
    model = TaskAssignee

    async def assign_many(
        self, session: AsyncSession, *, task_id: UUID, user_ids: list[UUID]
    ) -> None:
        if not user_ids:
            return
        instances = [
            self.model(task_id=task_id, user_id=user_id) for user_id in user_ids
        ]
        await self.add_and_flush_instances(session, instances)

    async def replace_all(
        self, session: AsyncSession, *, task_id: UUID, user_ids: list[UUID]
    ) -> None:
        await self.delete_by(session, task_id=task_id)
        await self.assign_many(session, task_id=task_id, user_ids=user_ids)

    async def remove_for_project(
        self, session: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> None:
        """Unassigns a user from every task in one project — used when
        they lose project membership, so an ex-member never lingers as
        an assignee."""
        task_ids = select(Task.id).where(Task.project_id == project_id)
        stmt = delete(self.model).where(
            self.model.user_id == user_id, self.model.task_id.in_(task_ids)
        )
        await session.execute(stmt)

    async def remove_for_org(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> None:
        """Unassigns a user from every task across every project in one
        org — used by the org-membership-removal cascade."""
        task_ids = (
            select(Task.id)
            .join(Project, Project.id == Task.project_id)
            .where(Project.org_id == org_id)
        )
        stmt = delete(self.model).where(
            self.model.user_id == user_id, self.model.task_id.in_(task_ids)
        )
        await session.execute(stmt)


task_assignee_repository = TaskAssigneeRepository()
