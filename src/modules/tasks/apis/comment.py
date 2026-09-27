from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from core.dependencies import AuthenticatedUser, DBSession, PaginationParams
from core.pagination import Page
from modules.projects.dependencies import AnyProjectMember
from modules.tasks.exceptions import (
    CommentNotFoundError,
    NotCommentAuthorError,
    TaskNotFoundError,
)
from modules.tasks.schemas import (
    CommentCreateRequest,
    CommentResponse,
    CommentUpdateRequest,
)
from modules.tasks.services import comment_service

comment_router = APIRouter(tags=["Comments"])


@comment_router.post(
    "/projects/{project_id}/tasks/{task_id}/comments",
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    project_id: UUID,
    task_id: UUID,
    body: CommentCreateRequest,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
) -> CommentResponse:
    try:
        return await comment_service.add_comment(
            session,
            project_id=project_id,
            task_id=task_id,
            user_id=user.id,
            body=body.body,
        )
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")


@comment_router.get("/projects/{project_id}/tasks/{task_id}/comments")
async def list_comments(
    project_id: UUID,
    task_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    pagination: PaginationParams,
) -> Page[CommentResponse]:
    try:
        return await comment_service.list_for_task(
            session,
            project_id=project_id,
            task_id=task_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")


@comment_router.patch("/projects/{project_id}/tasks/{task_id}/comments/{comment_id}")
async def update_comment(
    project_id: UUID,
    task_id: UUID,
    comment_id: UUID,
    body: CommentUpdateRequest,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
) -> CommentResponse:
    try:
        return await comment_service.update_comment(
            session,
            project_id=project_id,
            task_id=task_id,
            comment_id=comment_id,
            user_id=user.id,
            body=body.body,
        )
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    except CommentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    except NotCommentAuthorError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the comment's author can update it"
        )


@comment_router.delete(
    "/projects/{project_id}/tasks/{task_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    project_id: UUID,
    task_id: UUID,
    comment_id: UUID,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
) -> None:
    try:
        await comment_service.delete_comment(
            session,
            project_id=project_id,
            task_id=task_id,
            comment_id=comment_id,
            user_id=user.id,
        )
    except TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    except CommentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    except NotCommentAuthorError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the comment's author can delete it"
        )
