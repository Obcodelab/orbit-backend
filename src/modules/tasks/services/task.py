from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import Page
from core.types import SortOrder
from modules.organizations.schemas import MemberUserSummary
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.models import Project, ProjectMember
from modules.projects.repositories import (
    ActivityLogRepository,
    ProjectMemberRepository,
    ProjectRepository,
    activity_log_repository,
    project_member_repository,
    project_repository,
)
from modules.projects.types import ActivityAction, ProjectRole, ProjectStatus
from modules.tasks.exceptions import (
    AssigneeNotProjectMemberError,
    ParentTaskNotFoundError,
    StatusChangeForbiddenError,
    TaskNotFoundError,
)
from modules.tasks.models import Task
from modules.tasks.repositories import (
    TaskAssigneeRepository,
    TaskRepository,
    task_assignee_repository,
    task_repository,
)
from modules.tasks.schemas import TaskResponse
from modules.tasks.types import TaskPriority, TaskSortField, TaskStatus


def _build_response(task: Task) -> TaskResponse:
    return TaskResponse(
        task_id=task.id,
        key=f"{task.project.key}-{task.number}",
        parent_task_id=task.parent_task_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        labels=task.labels,
        due_date=task.due_date,
        resolved_at=task.resolved_at,
        created_by=task.created_by,
        assignees=[MemberUserSummary.model_validate(a.user) for a in task.assignees],
    )


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        assignee_repo: TaskAssigneeRepository,
        project_repo: ProjectRepository,
        project_member_repo: ProjectMemberRepository,
        activity_repo: ActivityLogRepository,
    ) -> None:
        self.task_repo = task_repo
        self.assignee_repo = assignee_repo
        self.project_repo = project_repo
        self.project_member_repo = project_member_repo
        self.activity_repo = activity_repo

    async def _validate_assignees(
        self, session: AsyncSession, *, project_id: UUID, user_ids: list[UUID]
    ) -> None:
        if not user_ids:
            return
        member_ids = await self.project_member_repo.get_member_user_ids(
            session, project_id=project_id, user_ids=user_ids
        )
        if set(user_ids) - member_ids:
            raise AssigneeNotProjectMemberError

    async def _validate_parent(
        self, session: AsyncSession, *, project_id: UUID, parent_task_id: UUID | None
    ) -> None:
        if parent_task_id is None:
            return
        parent = await self.task_repo.get_scoped(
            session, project_id=project_id, task_id=parent_task_id
        )
        if not parent:
            raise ParentTaskNotFoundError

    async def create_task(
        self,
        session: AsyncSession,
        *,
        project: Project,
        title: str,
        description: str | None,
        assignee_ids: list[UUID],
        parent_task_id: UUID | None,
        priority: TaskPriority,
        labels: str | None,
        due_date: date | None,
        creator_id: UUID,
    ) -> TaskResponse:
        if project.status == ProjectStatus.ARCHIVED:
            raise ProjectArchivedError

        await self._validate_assignees(
            session, project_id=project.id, user_ids=assignee_ids
        )
        await self._validate_parent(
            session, project_id=project.id, parent_task_id=parent_task_id
        )

        number = await self.project_repo.increment_task_counter(
            session, project_id=project.id
        )
        task = await self.task_repo.create_task(
            session,
            org_id=project.org_id,
            project_id=project.id,
            number=number,
            parent_task_id=parent_task_id,
            title=title,
            description=description,
            priority=priority,
            labels=labels,
            due_date=due_date,
            created_by=creator_id,
        )
        await self.assignee_repo.assign_many(
            session, task_id=task.id, user_ids=assignee_ids
        )
        await self.activity_repo.log(
            session,
            org_id=project.org_id,
            project_id=project.id,
            actor_id=creator_id,
            action=ActivityAction.TASK_CREATED,
            target=str(task.id),
        )

        task = await self.task_repo.get_scoped_with_assignees(
            session, project_id=project.id, task_id=task.id
        )
        return _build_response(task)

    async def list_for_project(
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
    ) -> Page[TaskResponse]:
        tasks, total = await self.task_repo.get_for_project(
            session,
            project_id=project_id,
            status_filter=status_filter,
            priority_filter=priority_filter,
            assignee_id=assignee_id,
            label=label,
            parent_id=parent_id,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        )
        items = [_build_response(t) for t in tasks]
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def get_task(
        self, session: AsyncSession, *, project_id: UUID, task_id: UUID
    ) -> TaskResponse:
        task = await self.task_repo.get_scoped_with_assignees(
            session, project_id=project_id, task_id=task_id
        )
        if not task:
            raise TaskNotFoundError
        return _build_response(task)

    async def update_task(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        updates: dict,
        assignee_ids: list[UUID] | None,
    ) -> tuple[TaskResponse, list[UUID]]:
        """Returns the task plus any newly added assignee ids — callers
        should notify only this diff, not everyone in assignee_ids, or
        an unrelated edit re-notifies people already assigned."""
        task = await self.task_repo.get_scoped(
            session, project_id=project_id, task_id=task_id
        )
        if not task:
            raise TaskNotFoundError

        if "parent_task_id" in updates:
            await self._validate_parent(
                session, project_id=project_id, parent_task_id=updates["parent_task_id"]
            )

        newly_added: list[UUID] = []
        if assignee_ids is not None:
            await self._validate_assignees(
                session, project_id=project_id, user_ids=assignee_ids
            )
            old_assignee_ids = await self.assignee_repo.get_user_ids_for_task(
                session, task_id=task.id
            )
            newly_added = [uid for uid in assignee_ids if uid not in old_assignee_ids]
            await self.assignee_repo.replace_all(
                session, task_id=task.id, user_ids=assignee_ids
            )

        if updates:
            await self.task_repo.update_fields(session, task=task, updates=updates)

        task = await self.task_repo.get_scoped_with_assignees(
            session, project_id=project_id, task_id=task_id
        )
        return _build_response(task), newly_added

    async def update_status(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        status: TaskStatus,
        caller: ProjectMember,
    ) -> TaskResponse:
        task = await self.task_repo.get_scoped_with_assignees(
            session, project_id=project_id, task_id=task_id
        )
        if not task:
            raise TaskNotFoundError

        is_privileged = caller.role in (ProjectRole.OWNER, ProjectRole.ADMIN)
        is_assignee = any(a.user_id == caller.user_id for a in task.assignees)
        if not is_privileged and not is_assignee:
            raise StatusChangeForbiddenError

        task.status = status
        task.resolved_at = datetime.now(UTC) if status == TaskStatus.DONE else None
        await self.task_repo.flush_and_refresh(session, task)
        await self.activity_repo.log(
            session,
            org_id=task.org_id,
            project_id=project_id,
            actor_id=caller.user_id,
            action=ActivityAction.TASK_STATUS_CHANGED,
            target=str(task.id),
        )
        return _build_response(task)

    async def delete_task(
        self, session: AsyncSession, *, project_id: UUID, task_id: UUID
    ) -> None:
        task = await self.task_repo.get_scoped(
            session, project_id=project_id, task_id=task_id
        )
        if not task:
            raise TaskNotFoundError
        await self.task_repo.delete_by_id(session, task.id)


task_service = TaskService(
    task_repo=task_repository,
    assignee_repo=task_assignee_repository,
    project_repo=project_repository,
    project_member_repo=project_member_repository,
    activity_repo=activity_log_repository,
)
