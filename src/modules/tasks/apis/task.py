from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from core.dependencies import AuthenticatedUser, DBSession, PaginationParams
from core.notifications import notify_many
from core.pagination import Page
from core.types import RealtimeEventType, SortOrder
from core.websocket_manager import build_event, connection_manager
from modules.projects.dependencies import AnyProjectMember, ProjectAdminOrOwner
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.repositories import project_repository
from modules.tasks.exceptions import (
    AssigneeNotProjectMemberError,
    ParentTaskNotFoundError,
    StatusChangeForbiddenError,
    TaskNotFoundError,
)
from modules.tasks.schemas import (
    TaskCreateRequest,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskUpdateRequest,
)
from modules.tasks.services import task_service
from modules.tasks.types import TaskPriority, TaskSortField, TaskStatus

task_router = APIRouter(tags=["Tasks"])


@task_router.post("/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: UUID,
    body: TaskCreateRequest,
    user: AuthenticatedUser,
    session: DBSession,
    membership: ProjectAdminOrOwner,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    project = await project_repository.get_by_id(session, project_id)
    try:
        task = await task_service.create_task(
            session,
            project=project,
            title=body.title,
            description=body.description,
            assignee_ids=body.assignee_ids,
            parent_task_id=body.parent_task_id,
            priority=body.priority,
            labels=body.labels,
            due_date=body.due_date,
            creator_id=user.id,
        )
    except ProjectArchivedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This project is archived and is read-only"
        )
    except AssigneeNotProjectMemberError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "All assignees must be members of this project",
        )
    except ParentTaskNotFoundError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "parent_task_id doesn't exist in this project"
        )

    event = build_event(
        event_type=RealtimeEventType.TASK_CREATED,
        project_id=project_id,
        data=task.model_dump(mode="json"),
        actor_id=user.id,
    )
    await connection_manager.broadcast(project_id, event)
    if task.assignees:
        background_tasks.add_task(
            notify_many, [a.user_id for a in task.assignees], event
        )
    return task


@task_router.get("/projects/{project_id}/tasks")
async def list_tasks(
    project_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    pagination: PaginationParams,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority_filter: TaskPriority | None = Query(default=None, alias="priority"),
    assignee_id: UUID | None = Query(default=None, alias="assignee"),
    label: str | None = Query(default=None),
    parent_id: UUID | None = Query(default=None),
    sort: TaskSortField | None = Query(default=None),
    order: SortOrder | None = Query(default=None),
) -> Page[TaskResponse]:
    return await task_service.list_for_project(
        session,
        project_id=project_id,
        status_filter=status_filter,
        priority_filter=priority_filter,
        assignee_id=assignee_id,
        label=label,
        parent_id=parent_id,
        sort=sort,
        order=order,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@task_router.get("/projects/{project_id}/tasks/{task_id}")
async def get_task(
    project_id: UUID,
    task_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
) -> TaskResponse:
    try:
        return await task_service.get_task(
            session, project_id=project_id, task_id=task_id
        )
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")


@task_router.patch("/projects/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskUpdateRequest,
    session: DBSession,
    membership: ProjectAdminOrOwner,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    data = body.model_dump(exclude_unset=True)
    assignee_ids = data.pop("assignee_ids", None)
    try:
        task, newly_added_assignees = await task_service.update_task(
            session,
            project_id=project_id,
            task_id=task_id,
            updates=data,
            assignee_ids=assignee_ids,
        )
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    except AssigneeNotProjectMemberError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "All assignees must be members of this project",
        )
    except ParentTaskNotFoundError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "parent_task_id doesn't exist in this project"
        )

    event = build_event(
        event_type=RealtimeEventType.TASK_UPDATED,
        project_id=project_id,
        data=task.model_dump(mode="json"),
        actor_id=membership.user_id,
    )
    await connection_manager.broadcast(project_id, event)
    if newly_added_assignees:
        background_tasks.add_task(notify_many, newly_added_assignees, event)
    return task


@task_router.patch("/projects/{project_id}/tasks/{task_id}/status")
async def update_task_status(
    project_id: UUID,
    task_id: UUID,
    body: TaskStatusUpdateRequest,
    session: DBSession,
    membership: AnyProjectMember,
) -> TaskResponse:
    try:
        task = await task_service.update_status(
            session,
            project_id=project_id,
            task_id=task_id,
            status=body.status,
            caller=membership,
        )
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    except StatusChangeForbiddenError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the task's assignees or a project admin/owner can change its status",
        )

    await connection_manager.broadcast(
        project_id,
        build_event(
            event_type=RealtimeEventType.TASK_STATUS_CHANGED,
            project_id=project_id,
            data=task.model_dump(mode="json"),
            actor_id=membership.user_id,
        ),
    )
    return task


@task_router.delete(
    "/projects/{project_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    session: DBSession,
    membership: ProjectAdminOrOwner,
) -> None:
    try:
        await task_service.delete_task(session, project_id=project_id, task_id=task_id)
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")

    await connection_manager.broadcast(
        project_id,
        build_event(
            event_type=RealtimeEventType.TASK_DELETED,
            project_id=project_id,
            data={"task_id": str(task_id)},
            actor_id=membership.user_id,
        ),
    )
