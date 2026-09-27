from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import Page
from modules.projects.repositories import ActivityLogRepository, activity_log_repository
from modules.projects.types import ActivityAction
from modules.tasks.exceptions import (
    CommentNotFoundError,
    NotCommentAuthorError,
    TaskNotFoundError,
)
from modules.tasks.models import Comment
from modules.tasks.repositories import (
    CommentRepository,
    TaskRepository,
    comment_repository,
    task_repository,
)
from modules.tasks.schemas import CommentResponse


class CommentService:
    def __init__(
        self,
        comment_repo: CommentRepository,
        task_repo: TaskRepository,
        activity_repo: ActivityLogRepository,
    ) -> None:
        self.comment_repo = comment_repo
        self.task_repo = task_repo
        self.activity_repo = activity_repo

    async def add_comment(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        user_id: UUID,
        body: str,
    ) -> CommentResponse:
        task = await self.task_repo.get_scoped(
            session, project_id=project_id, task_id=task_id
        )
        if not task:
            raise TaskNotFoundError

        comment = await self.comment_repo.create_comment(
            session, task_id=task_id, user_id=user_id, body=body
        )
        await self.activity_repo.log(
            session,
            org_id=task.org_id,
            project_id=project_id,
            actor_id=user_id,
            action=ActivityAction.COMMENT_ADDED,
            target=str(task_id),
        )

        comment_with_user = await self.comment_repo.get_by_id_with_user(
            session, comment_id=comment.id
        )
        return CommentResponse.model_validate(comment_with_user)

    async def list_for_task(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        limit: int,
        offset: int,
    ) -> Page[CommentResponse]:
        task = await self.task_repo.get_scoped(
            session, project_id=project_id, task_id=task_id
        )
        if not task:
            raise TaskNotFoundError

        comments, total = await self.comment_repo.get_for_task(
            session, task_id=task_id, limit=limit, offset=offset
        )
        items = [CommentResponse.model_validate(c) for c in comments]
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def _get_owned_comment(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        comment_id: UUID,
        user_id: UUID,
    ) -> Comment:
        task = await self.task_repo.get_scoped(
            session, project_id=project_id, task_id=task_id
        )
        if not task:
            raise TaskNotFoundError

        comment = await self.comment_repo.get_scoped(
            session, task_id=task_id, comment_id=comment_id
        )
        if not comment:
            raise CommentNotFoundError
        if comment.user_id != user_id:
            raise NotCommentAuthorError

        return comment

    async def update_comment(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        comment_id: UUID,
        user_id: UUID,
        body: str,
    ) -> CommentResponse:
        comment = await self._get_owned_comment(
            session,
            project_id=project_id,
            task_id=task_id,
            comment_id=comment_id,
            user_id=user_id,
        )
        await self.comment_repo.update_body(session, comment=comment, body=body)
        comment_with_user = await self.comment_repo.get_by_id_with_user(
            session, comment_id=comment.id
        )
        return CommentResponse.model_validate(comment_with_user)

    async def delete_comment(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        comment_id: UUID,
        user_id: UUID,
    ) -> None:
        comment = await self._get_owned_comment(
            session,
            project_id=project_id,
            task_id=task_id,
            comment_id=comment_id,
            user_id=user_id,
        )
        await self.comment_repo.delete_by_id(session, comment.id)


comment_service = CommentService(
    comment_repo=comment_repository,
    task_repo=task_repository,
    activity_repo=activity_log_repository,
)
