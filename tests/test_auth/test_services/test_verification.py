from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.exceptions import VerificationCooldownError
from modules.auth.models import User
from modules.auth.repositories import user_repository, verification_code_repository
from modules.auth.services import verification_service
from modules.auth.types import LoginMethod, VerificationPurpose


async def _make_user(db_session: AsyncSession) -> User:
    return await user_repository.create_user(
        db_session,
        email="verification-service-test@example.com",
        first_name="Test",
        last_name="User",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def test_check_resend_cooldown_raises_when_code_is_fresh(
    db_session: AsyncSession,
):
    user = await _make_user(db_session)
    await verification_service.send_email_verification_code(db_session, user)

    try:
        await verification_service.check_resend_cooldown(
            db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
        )
        raise AssertionError("expected VerificationCooldownError")
    except VerificationCooldownError as exc:
        assert exc.retry_after_seconds > 0


async def test_check_resend_cooldown_passes_once_window_elapses(
    db_session: AsyncSession,
):
    user = await _make_user(db_session)
    await verification_service.send_email_verification_code(db_session, user)

    code_row = await verification_code_repository.get_by(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )
    code_row.created_at = datetime.now(UTC) - timedelta(seconds=61)
    await db_session.flush()

    await verification_service.check_resend_cooldown(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )  # does not raise


async def test_check_resend_cooldown_passes_when_no_code_exists(
    db_session: AsyncSession,
):
    user = await _make_user(db_session)

    await verification_service.check_resend_cooldown(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )  # does not raise — nothing to be in cooldown from


async def test_resend_reuses_same_code_once_cooldown_has_passed(
    db_session: AsyncSession,
):
    user = await _make_user(db_session)
    await verification_service.send_email_verification_code(db_session, user)
    original = await verification_code_repository.get_by(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )
    original_code = original.code
    original.created_at = datetime.now(UTC) - timedelta(seconds=61)
    await db_session.flush()

    await verification_service.send_email_verification_code(db_session, user)

    current = await verification_code_repository.get_by(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )
    assert current.code == original_code


async def test_resend_issues_fresh_code_once_expired(db_session: AsyncSession):
    user = await _make_user(db_session)
    await verification_service.send_email_verification_code(db_session, user)
    original = await verification_code_repository.get_by(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )
    original_code = original.code
    original.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    await verification_service.send_email_verification_code(db_session, user)

    current = await verification_code_repository.get_by(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )
    assert current.code != original_code
