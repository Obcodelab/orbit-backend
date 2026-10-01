from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from core.types import SortOrder
from modules.ai.models import AIConversation


class AIConversationRepository(BaseRepository[AIConversation]):
    model = AIConversation

    async def create_conversation(
        self, session: AsyncSession, *, org_id: UUID, project_id: UUID, user_id: UUID
    ) -> AIConversation:
        return await self.create(
            session, org_id=org_id, project_id=project_id, user_id=user_id
        )

    async def get_scoped(
        self, session: AsyncSession, *, project_id: UUID, conversation_id: UUID
    ) -> AIConversation | None:
        return await self.get_by(session, id=conversation_id, project_id=project_id)

    async def set_title(
        self, session: AsyncSession, *, conversation: AIConversation, title: str
    ) -> AIConversation:
        conversation.title = title
        return await self.flush_and_refresh(session, conversation)

    async def get_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AIConversation], int]:
        stmt = select(self.model).where(self.model.project_id == project_id)
        total = await self._count(session, stmt)
        stmt = self._apply_order(
            stmt,
            order=order,
            column=self.model.created_at,
            default_order=SortOrder.DESC,
        )
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


ai_conversation_repository = AIConversationRepository()
