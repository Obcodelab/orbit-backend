from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from core.types import SortOrder
from modules.ai.models import AIMessage
from modules.ai.types import AIMessageRole, CitationDict


class AIMessageRepository(BaseRepository[AIMessage]):
    model = AIMessage

    async def create_message(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        role: AIMessageRole,
        content: str,
        citations: list[CitationDict] | None = None,
    ) -> AIMessage:
        return await self.create(
            session,
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
        )

    async def get_for_conversation(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AIMessage], int]:
        """Defaults to ascending — a chat transcript reads oldest-first,
        unlike most other lists in this app which default to newest-first."""
        stmt = select(self.model).where(self.model.conversation_id == conversation_id)
        total = await self._count(session, stmt)
        stmt = self._apply_order(
            stmt,
            order=order,
            column=self.model.created_at,
            default_order=SortOrder.ASC,
        )
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


ai_message_repository = AIMessageRepository()
