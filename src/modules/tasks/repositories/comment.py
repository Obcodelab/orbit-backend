from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from modules.tasks.models import Comment


class CommentRepository(BaseRepository[Comment]):
    model = Comment

    async def create_comment(
        self, session: AsyncSession, *, task_id: UUID, user_id: UUID, body: str
    ) -> Comment:
        return await self.create(session, task_id=task_id, user_id=user_id, body=body)

    async def get_by_id_with_user(
        self, session: AsyncSession, *, comment_id: UUID
    ) -> Comment | None:
        stmt = (
            select(self.model)
            .where(self.model.id == comment_id)
            .options(selectinload(self.model.user))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scoped(
        self, session: AsyncSession, *, task_id: UUID, comment_id: UUID
    ) -> Comment | None:
        return await self.get_by(session, id=comment_id, task_id=task_id)

    async def update_body(
        self, session: AsyncSession, *, comment: Comment, body: str
    ) -> Comment:
        comment.body = body
        return await self.flush_and_refresh(session, comment)

    async def get_for_task(
        self, session: AsyncSession, *, task_id: UUID, limit: int, offset: int
    ) -> tuple[list[Comment], int]:
        stmt = select(self.model).where(self.model.task_id == task_id)
        total = await self._count(session, stmt)
        stmt = (
            stmt.options(selectinload(self.model.user))
            .order_by(self.model.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


comment_repository = CommentRepository()
