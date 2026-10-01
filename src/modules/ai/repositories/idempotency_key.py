from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from modules.ai.models import AskIdempotencyKey


class AskIdempotencyKeyRepository(BaseRepository[AskIdempotencyKey]):
    model = AskIdempotencyKey

    async def get_message_id(
        self, session: AsyncSession, *, user_id: UUID, key: str
    ) -> UUID | None:
        record = await self.get_by(session, user_id=user_id, key=key)
        return record.message_id if record else None

    async def record(
        self, session: AsyncSession, *, user_id: UUID, key: str, message_id: UUID
    ) -> None:
        await self.create(session, user_id=user_id, key=key, message_id=message_id)


ask_idempotency_key_repository = AskIdempotencyKeyRepository()
