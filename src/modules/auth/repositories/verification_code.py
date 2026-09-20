import random
import string
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.repository import BaseRepository
from modules.auth.models import UserVerificationCode
from modules.auth.types import VerificationPurpose


class VerificationCodeRepository(BaseRepository[UserVerificationCode]):
    model = UserVerificationCode

    async def create_code(
        self, session: AsyncSession, *, user_id: UUID, purpose: VerificationPurpose
    ) -> UserVerificationCode:
        code = "".join(random.choices(string.digits, k=6))
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
        )
        return await self.create(
            session, user_id=user_id, code=code, purpose=purpose, expires_at=expires_at
        )

    async def get_valid_code(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        code: str,
        purpose: VerificationPurpose,
    ) -> UserVerificationCode | None:
        verification = await self.get_by(
            session, user_id=user_id, code=code, purpose=purpose
        )
        if not verification or verification.is_expired:
            return None
        return verification

    async def delete_for_user(
        self, session: AsyncSession, *, user_id: UUID, purpose: VerificationPurpose
    ) -> int:
        return await self.delete_by(session, user_id=user_id, purpose=purpose)

    async def get_latest_for_user(
        self, session: AsyncSession, *, user_id: UUID
    ) -> UserVerificationCode | None:
        """The most recent code for this user, regardless of purpose — a
        resend only ever makes sense for a code that already exists, so
        whatever's most recently outstanding tells us which purpose the
        caller means without them having to say so."""
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


verification_code_repository = VerificationCodeRepository()
