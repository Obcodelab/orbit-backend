from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.types import TokenType
from modules.auth.repositories import (
    BlacklistedTokenRepository,
    blacklisted_token_repository,
)


class BlacklistService:
    def __init__(self, repo: BlacklistedTokenRepository) -> None:
        self.repo = repo

    async def is_blacklisted(self, session: AsyncSession, jti: UUID) -> bool:
        return await self.repo.is_blacklisted(session, jti)

    async def blacklist_token(
        self,
        session: AsyncSession,
        *,
        jti: UUID,
        token_type: TokenType,
        expires_at: datetime,
    ) -> None:
        await self.repo.blacklist(
            session, jti=jti, token_type=token_type, expires_at=expires_at
        )

    async def cleanup_expired(self, session: AsyncSession) -> None:
        await self.repo.delete_expired(session)


blacklist_service = BlacklistService(repo=blacklisted_token_repository)
