from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from core.types import TokenType
from modules.auth.models import BlacklistedToken


class BlacklistedTokenRepository(BaseRepository[BlacklistedToken]):
    model = BlacklistedToken

    async def is_blacklisted(self, session: AsyncSession, jti: UUID) -> bool:
        return await self.get_by(session, jti=jti) is not None

    async def blacklist(
        self,
        session: AsyncSession,
        *,
        jti: UUID,
        token_type: TokenType,
        expires_at: datetime,
    ) -> BlacklistedToken:
        return await self.create(
            session, jti=jti, token_type=token_type, expires_at=expires_at
        )

    async def delete_expired(self, session: AsyncSession) -> int:
        stmt = delete(self.model).where(self.model.expires_at < datetime.now(UTC))
        result = await session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]


blacklisted_token_repository = BlacklistedTokenRepository()
