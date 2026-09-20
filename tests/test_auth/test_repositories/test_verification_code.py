from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import hash_password
from modules.auth.models import User, UserVerificationCode
from modules.auth.repositories import user_repository, verification_code_repository
from modules.auth.types import LoginMethod, VerificationPurpose


async def _make_user(db_session: AsyncSession) -> User:
    return await user_repository.create_user(
        db_session,
        email="repo-test@example.com",
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1"),
    )


async def test_create_code_generates_six_digit_code(db_session: AsyncSession):
    user = await _make_user(db_session)

    verification = await verification_code_repository.create_code(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )

    assert len(verification.code) == 6
    assert verification.code.isdigit()


async def test_create_code_sets_expiry_from_settings(db_session: AsyncSession):
    user = await _make_user(db_session)
    before = datetime.now(UTC)

    verification = await verification_code_repository.create_code(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )

    expected = before + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES)
    # small window for however long the test itself takes to run
    assert abs((verification.expires_at - expected).total_seconds()) < 5


async def test_get_valid_code_returns_none_for_expired_code(db_session: AsyncSession):
    user = await _make_user(db_session)
    verification = await verification_code_repository.create_code(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )
    verification.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    result = await verification_code_repository.get_valid_code(
        db_session,
        user_id=user.id,
        code=verification.code,
        purpose=VerificationPurpose.EMAIL_VERIFICATION,
    )

    assert result is None


async def test_get_valid_code_returns_none_for_wrong_purpose(db_session: AsyncSession):
    user = await _make_user(db_session)
    verification = await verification_code_repository.create_code(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )

    result = await verification_code_repository.get_valid_code(
        db_session,
        user_id=user.id,
        code=verification.code,
        purpose=VerificationPurpose.PASSWORD_RESET,
    )

    assert result is None


async def test_delete_for_user_only_deletes_matching_purpose(db_session: AsyncSession):
    """Repository-level version of the cross-purpose regression covered at
    the API level in test_apis/test_user.py — this one pins the exact query
    responsible, without a full register/verify HTTP round trip."""
    user = await _make_user(db_session)
    email_code = await verification_code_repository.create_code(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )
    reset_code = await verification_code_repository.create_code(
        db_session, user_id=user.id, purpose=VerificationPurpose.PASSWORD_RESET
    )

    await verification_code_repository.delete_for_user(
        db_session, user_id=user.id, purpose=VerificationPurpose.EMAIL_VERIFICATION
    )

    remaining = (
        await db_session.execute(
            select(UserVerificationCode).where(UserVerificationCode.id == email_code.id)
        )
    ).scalar_one_or_none()
    assert remaining is None

    still_there = (
        await db_session.execute(
            select(UserVerificationCode).where(UserVerificationCode.id == reset_code.id)
        )
    ).scalar_one_or_none()
    assert still_there is not None
