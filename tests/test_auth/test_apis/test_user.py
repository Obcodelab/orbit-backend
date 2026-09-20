from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.auth.models import User, UserVerificationCode
from modules.auth.types import VerificationPurpose

TEST_PASSWORD = "Password1!"


@pytest.fixture
def register_payload() -> dict:
    return {
        "email": "new@example.com",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
        "first_name": "New",
        "last_name": "User",
    }


async def test_register_creates_unverified_user(
    client: AsyncClient, db_session: AsyncSession, register_payload: dict
):
    response = await client.post("/api/v1/auth/register", json=register_payload)

    assert response.status_code == 201
    assert "detail" in response.json()

    user = (
        await db_session.execute(
            select(User).where(User.email == register_payload["email"])
        )
    ).scalar_one()
    assert user.email_verified is False
    assert user.password_hash is not None


async def test_register_rejects_mismatched_passwords(
    client: AsyncClient, register_payload: dict
):
    register_payload["confirm_password"] = "SomethingElse1!"

    response = await client.post("/api/v1/auth/register", json=register_payload)

    assert response.status_code == 422


async def test_register_reports_mismatch_before_weak_password(
    client: AsyncClient, register_payload: dict
):
    # both values are weak *and* differ — the mismatch should still be
    # what's reported, since strength is moot until they agree
    register_payload["password"] = "weak"
    register_payload["confirm_password"] = "alsoweak"

    response = await client.post("/api/v1/auth/register", json=register_payload)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert len(errors) == 1
    assert "do not match" in errors[0]["msg"]


async def test_register_duplicate_email_rejected(
    client: AsyncClient, register_payload: dict
):
    first = await client.post("/api/v1/auth/register", json=register_payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=register_payload)
    assert second.status_code == 409


async def test_register_weak_password_rejected(
    client: AsyncClient, register_payload: dict
):
    register_payload["password"] = "weak"

    response = await client.post("/api/v1/auth/register", json=register_payload)

    assert response.status_code == 422


async def test_login_before_verification_sends_code_not_tokens(
    client: AsyncClient, register_payload: dict
):
    await client.post("/api/v1/auth/register", json=register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" not in body
    assert "detail" in body


async def test_verify_email_with_correct_code_issues_tokens(
    client: AsyncClient,
    get_verification_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await client.post("/api/v1/auth/register", json=register_payload)
    code = await get_verification_code(register_payload["email"])

    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": code},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["email_verified"] is True


async def test_verify_email_with_wrong_code_rejected(
    client: AsyncClient, register_payload: dict
):
    await client.post("/api/v1/auth/register", json=register_payload)

    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": "000000"},
    )

    assert response.status_code == 400


async def test_login_after_verification_issues_tokens(
    client: AsyncClient,
    get_verification_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await client.post("/api/v1/auth/register", json=register_payload)
    code = await get_verification_code(register_payload["email"])
    await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": code},
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password_rejected(
    client: AsyncClient, register_payload: dict
):
    await client.post("/api/v1/auth/register", json=register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": "WrongPass1"},
    )

    assert response.status_code == 401


async def test_me_without_token_rejected(client: AsyncClient):
    response = await client.get("/api/v1/account/me")

    assert response.status_code == 401


async def test_me_with_valid_token_returns_profile(
    client: AsyncClient,
    get_verification_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await client.post("/api/v1/auth/register", json=register_payload)
    code = await get_verification_code(register_payload["email"])
    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": code},
    )
    access_token = verify.json()["access_token"]

    response = await client.get(
        "/api/v1/account/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == register_payload["email"]


async def test_logout_blacklists_access_token(
    client: AsyncClient,
    get_verification_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await client.post("/api/v1/auth/register", json=register_payload)
    code = await get_verification_code(register_payload["email"])
    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": code},
    )
    tokens = verify.json()

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout_response.status_code == 204

    me_response = await client.get(
        "/api/v1/account/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 401


# --- resend-code --------------------------------------------------------------


async def test_resend_code_within_cooldown_returns_429(
    client: AsyncClient,
    get_verification_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await client.post("/api/v1/auth/register", json=register_payload)
    original_code = await get_verification_code(register_payload["email"])

    response = await client.post(
        "/api/v1/auth/resend-code",
        json={"email": register_payload["email"]},
    )

    assert response.status_code == 429
    assert "Retry-After" in response.headers

    # cooldown blocked the resend — the original code is still untouched
    unaffected = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": original_code},
    )
    assert unaffected.status_code == 200


async def test_resend_code_unknown_email_returns_generic_response(
    client: AsyncClient,
):
    response = await client.post(
        "/api/v1/auth/resend-code", json={"email": "nobody@example.com"}
    )

    assert response.status_code == 200
    assert "detail" in response.json()


async def test_resend_code_with_nothing_outstanding_returns_generic_response(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    register_payload: dict,
):
    # verified, and never called forgot-password — no code exists to infer
    # a purpose from at all
    await register_and_verify(register_payload)

    response = await client.post(
        "/api/v1/auth/resend-code",
        json={"email": register_payload["email"]},
    )
    assert response.status_code == 200


async def test_resend_code_for_verified_user_is_a_noop(
    client: AsyncClient,
    db_session: AsyncSession,
    register_payload: dict,
):
    # unverified, so the outstanding code is EMAIL_VERIFICATION — but the
    # account gets verified through some other path before the resend lands
    await client.post("/api/v1/auth/register", json=register_payload)
    user = (
        await db_session.execute(
            select(User).where(User.email == register_payload["email"])
        )
    ).scalar_one()
    user.email_verified = True
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/resend-code",
        json={"email": register_payload["email"]},
    )
    assert response.status_code == 200

    remaining = (
        await db_session.execute(
            select(UserVerificationCode).where(
                UserVerificationCode.user_id == user.id,
                UserVerificationCode.purpose == VerificationPurpose.EMAIL_VERIFICATION,
            )
        )
    ).scalar_one_or_none()
    assert remaining is not None  # untouched — the endpoint no-op'd, not sent


async def test_resend_code_infers_password_reset_purpose(
    client: AsyncClient,
    db_session: AsyncSession,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    get_reset_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await register_and_verify(register_payload)
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": register_payload["email"]}
    )
    original_code = await get_reset_code(register_payload["email"])

    # past the cooldown, so the resend actually goes through
    code_row = (
        await db_session.execute(
            select(UserVerificationCode).where(
                UserVerificationCode.purpose == VerificationPurpose.PASSWORD_RESET
            )
        )
    ).scalar_one()
    code_row.created_at = datetime.now(UTC) - timedelta(seconds=61)
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/resend-code",
        json={"email": register_payload["email"]},
    )
    assert response.status_code == 200

    # no purpose was supplied — a password-reset code was still resent,
    # not an email-verification one, and it's usable via the reset flow
    resent_code = await get_reset_code(register_payload["email"])
    assert resent_code == original_code

    verify_response = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": register_payload["email"], "code": resent_code},
    )
    assert verify_response.status_code == 200


async def test_resend_code_reissues_after_expiry(
    client: AsyncClient,
    db_session: AsyncSession,
    get_verification_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await client.post("/api/v1/auth/register", json=register_payload)
    original_code = await get_verification_code(register_payload["email"])

    code_row = (
        await db_session.execute(
            select(UserVerificationCode).where(
                UserVerificationCode.purpose == VerificationPurpose.EMAIL_VERIFICATION
            )
        )
    ).scalar_one()
    code_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    # an expired code blocks neither the purpose inference nor the cooldown
    response = await client.post(
        "/api/v1/auth/resend-code",
        json={"email": register_payload["email"]},
    )
    assert response.status_code == 200

    fresh_code = await get_verification_code(register_payload["email"])
    assert fresh_code != original_code

    verify_response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": fresh_code},
    )
    assert verify_response.status_code == 200


# --- forgot-password / verify-reset-code / reset-password -------------------


async def test_forgot_password_unknown_email_returns_generic_response(
    client: AsyncClient,
):
    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
    )

    assert response.status_code == 200
    assert "detail" in response.json()


async def test_full_password_reset_flow(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    get_reset_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await register_and_verify(register_payload)

    forgot_response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": register_payload["email"]}
    )
    assert forgot_response.status_code == 200
    reset_code = await get_reset_code(register_payload["email"])

    verify_response = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": register_payload["email"], "code": reset_code},
    )
    assert verify_response.status_code == 200
    reset_token = verify_response.json()["reset_token"]

    new_password = "NewPassword1!"
    reset_response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": new_password,
            "confirm_new_password": new_password,
        },
    )
    assert reset_response.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": new_password},
    )
    assert new_login.status_code == 200


async def test_reset_password_rejects_mismatched_passwords(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    get_reset_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await register_and_verify(register_payload)
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": register_payload["email"]}
    )
    reset_code = await get_reset_code(register_payload["email"])
    verify_response = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": register_payload["email"], "code": reset_code},
    )
    reset_token = verify_response.json()["reset_token"]

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": "NewPassword1!",
            "confirm_new_password": "SomethingElse1!",
        },
    )
    assert response.status_code == 422


async def test_reset_token_cannot_be_reused(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    get_reset_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    await register_and_verify(register_payload)
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": register_payload["email"]}
    )
    reset_code = await get_reset_code(register_payload["email"])
    verify_response = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": register_payload["email"], "code": reset_code},
    )
    reset_token = verify_response.json()["reset_token"]

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": "NewPassword1!",
            "confirm_new_password": "NewPassword1!",
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": "AnotherPass2!",
            "confirm_new_password": "AnotherPass2!",
        },
    )
    assert second.status_code == 400


async def test_verifying_email_does_not_invalidate_pending_reset_code(
    client: AsyncClient,
    get_verification_code: Callable[[str], Awaitable[str]],
    get_reset_code: Callable[[str], Awaitable[str]],
    register_payload: dict,
):
    """Regression test: verify_code used to delete *all* of a user's codes,
    not just the ones for the purpose that was actually satisfied."""
    await client.post("/api/v1/auth/register", json=register_payload)

    # forgot-password doesn't require a verified email
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": register_payload["email"]}
    )

    email_code = await get_verification_code(register_payload["email"])
    await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": email_code},
    )

    reset_code = await get_reset_code(register_payload["email"])
    response = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": register_payload["email"], "code": reset_code},
    )
    assert response.status_code == 200


# --- change-password (authenticated) -----------------------------------------


async def test_change_password_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/account/change-password",
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "NewPassword1!",
            "confirm_new_password": "NewPassword1!",
        },
    )
    assert response.status_code == 401


async def test_change_password_success(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    register_payload: dict,
):
    tokens = await register_and_verify(register_payload)

    response = await client.post(
        "/api/v1/account/change-password",
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "NewPassword1!",
            "confirm_new_password": "NewPassword1!",
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": "NewPassword1!"},
    )
    assert new_login.status_code == 200


async def test_change_password_wrong_current_password_rejected(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    register_payload: dict,
):
    tokens = await register_and_verify(register_payload)

    response = await client.post(
        "/api/v1/account/change-password",
        json={
            "current_password": "WrongPassword1!",
            "new_password": "NewPassword1!",
            "confirm_new_password": "NewPassword1!",
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 400


async def test_change_password_rejects_mismatched_passwords(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    register_payload: dict,
):
    tokens = await register_and_verify(register_payload)

    response = await client.post(
        "/api/v1/account/change-password",
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "NewPassword1!",
            "confirm_new_password": "SomethingElse1!",
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 422


# --- profile (GET/PATCH /me) --------------------------------------------------


async def test_update_profile_requires_auth(client: AsyncClient):
    response = await client.patch("/api/v1/account/me", json={"first_name": "X"})
    assert response.status_code == 401


async def test_update_profile_success(
    client: AsyncClient,
    register_and_verify: Callable[[dict], Awaitable[dict]],
    register_payload: dict,
):
    tokens = await register_and_verify(register_payload)

    response = await client.patch(
        "/api/v1/account/me",
        json={"first_name": "Updated"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Updated"
    assert body["last_name"] == register_payload["last_name"]


# --- rate limiting ------------------------------------------------------------


async def test_login_is_rate_limited(client: AsyncClient, register_payload: dict):
    limit = int(settings.RATE_LIMIT_AUTH.split("/")[0])

    for _ in range(limit):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": register_payload["email"], "password": "WrongPass1!"},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": "WrongPass1!"},
    )
    assert blocked.status_code == 429
