from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.email import send_email_mock
from modules.auth.exceptions import VerificationCooldownError
from modules.auth.models import User, UserVerificationCode
from modules.auth.repositories import (
    VerificationCodeRepository,
    verification_code_repository,
)
from modules.auth.types import VerificationPurpose

_SEND_COPY: dict[VerificationPurpose, tuple[str, str]] = {
    VerificationPurpose.EMAIL_VERIFICATION: ("Verify your email", "verification code"),
    VerificationPurpose.PASSWORD_RESET: ("Reset your password", "password reset code"),
}


class VerificationService:
    def __init__(self, verification_repo: VerificationCodeRepository) -> None:
        self.verification_repo = verification_repo

    async def _get_sendable_code(
        self, session: AsyncSession, *, user_id: UUID, purpose: VerificationPurpose
    ) -> UserVerificationCode | None:
        """Reuses a still-valid code rather than reissuing on every call — a
        resend shouldn't invalidate a code the user already has open in an
        email tab, and reuse doesn't make guessing any easier than reissuing
        would. Within the cooldown window, returns None (caller no-ops);
        past it but still valid, returns the existing code to resend as-is;
        expired or missing, clears it out and mints a fresh one."""
        existing = await self.verification_repo.get_by(
            session, user_id=user_id, purpose=purpose
        )

        if existing and not existing.is_expired:
            age = (datetime.now(UTC) - existing.created_at).total_seconds()
            if age < settings.VERIFICATION_RESEND_COOLDOWN_SECONDS:
                return None
            return existing

        await self.verification_repo.delete_for_user(
            session, user_id=user_id, purpose=purpose
        )
        return await self.verification_repo.create_code(
            session, user_id=user_id, purpose=purpose
        )

    async def check_resend_cooldown(
        self, session: AsyncSession, *, user_id: UUID, purpose: VerificationPurpose
    ) -> None:
        """Raises VerificationCooldownError if a code for this purpose was
        already sent within the cooldown window. Only the explicit resend
        endpoint calls this — register/login's auto-send stay silent."""
        existing = await self.verification_repo.get_by(
            session, user_id=user_id, purpose=purpose
        )
        if not existing or existing.is_expired:
            return

        age = (datetime.now(UTC) - existing.created_at).total_seconds()
        remaining = settings.VERIFICATION_RESEND_COOLDOWN_SECONDS - age
        if remaining > 0:
            raise VerificationCooldownError(retry_after_seconds=int(remaining) + 1)

    async def send_code(
        self, session: AsyncSession, user: User, purpose: VerificationPurpose
    ) -> None:
        """Purpose-agnostic send, used directly by the unified resend
        endpoint. The two named wrappers below exist purely so call sites
        that always know their purpose statically (register, login) read
        clearly, without a raw enum literal at every call."""
        verification = await self._get_sendable_code(
            session, user_id=user.id, purpose=purpose
        )
        if verification is None:
            return  # within cooldown — caller still reports success

        subject, label = _SEND_COPY[purpose]
        send_email_mock(
            user.email,
            subject,
            f"Your {label} is {verification.code}. It expires in "
            f"{settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes.",
        )

    async def send_email_verification_code(
        self, session: AsyncSession, user: User
    ) -> None:
        await self.send_code(session, user, VerificationPurpose.EMAIL_VERIFICATION)

    async def send_password_reset_code(self, session: AsyncSession, user: User) -> None:
        await self.send_code(session, user, VerificationPurpose.PASSWORD_RESET)

    async def verify_code(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        code: str,
        purpose: VerificationPurpose,
    ) -> bool:
        verification = await self.verification_repo.get_valid_code(
            session, user_id=user_id, code=code, purpose=purpose
        )
        if not verification:
            return False
        # Scoped to this purpose only — an EMAIL_VERIFICATION success must
        # not wipe out an unrelated, still-pending PASSWORD_RESET code.
        await self.verification_repo.delete_for_user(
            session, user_id=user_id, purpose=purpose
        )
        return True


verification_service = VerificationService(
    verification_repo=verification_code_repository
)
