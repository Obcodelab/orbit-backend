from datetime import UTC, datetime, timedelta

import jwt

from core.config import settings
from core.exceptions import TokenExpiredError, TokenInvalidError
from core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_hash_password_does_not_store_plaintext():
    hashed = hash_password("Password1")

    assert hashed != "Password1"


def test_verify_password_accepts_correct_password():
    hashed = hash_password("Password1")

    assert verify_password("Password1", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("Password1")

    assert verify_password("WrongPassword1", hashed) is False


def test_create_access_token_round_trips_claims():
    token, expires_at = create_access_token({"sub": "user-123"})

    claims = decode_token(token)

    assert claims["sub"] == "user-123"
    assert claims["type"] == TokenType.ACCESS
    assert "jti" in claims
    assert isinstance(expires_at, datetime)


def test_create_refresh_token_has_refresh_type():
    token, _ = create_refresh_token({"sub": "user-123"})

    claims = decode_token(token)

    assert claims["type"] == TokenType.REFRESH


def test_create_reset_token_has_reset_type():
    token, _ = create_reset_token({"sub": "user-123"})

    claims = decode_token(token)

    assert claims["type"] == TokenType.RESET


def test_access_and_refresh_tokens_get_distinct_jti():
    access_token, _ = create_access_token({"sub": "user-123"})
    refresh_token, _ = create_refresh_token({"sub": "user-123"})

    assert decode_token(access_token)["jti"] != decode_token(refresh_token)["jti"]


def test_decode_token_rejects_expired_token():
    now = datetime.now(UTC)
    expired_payload = {
        "sub": "user-123",
        "type": TokenType.ACCESS.value,
        "jti": "test-jti",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired_token = jwt.encode(
        expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    try:
        decode_token(expired_token)
        raise AssertionError("expected TokenExpiredError")
    except TokenExpiredError:
        pass


def test_decode_token_rejects_garbage_string():
    try:
        decode_token("not-a-real-token")
        raise AssertionError("expected TokenInvalidError")
    except TokenInvalidError:
        pass


def test_decode_token_rejects_wrong_signature():
    token, _ = create_access_token({"sub": "user-123"})
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    try:
        decode_token(tampered)
        raise AssertionError("expected TokenInvalidError")
    except TokenInvalidError:
        pass


def test_validate_password_strength_accepts_strong_password():
    assert validate_password_strength("Password1!") == "Password1!"


def test_validate_password_strength_rejects_too_short():
    try:
        validate_password_strength("Pw1!")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_validate_password_strength_rejects_missing_uppercase():
    try:
        validate_password_strength("password1!")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_validate_password_strength_rejects_missing_lowercase():
    try:
        validate_password_strength("PASSWORD1!")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_validate_password_strength_rejects_missing_digit():
    try:
        validate_password_strength("Password!")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_validate_password_strength_rejects_missing_special_character():
    try:
        validate_password_strength("Password1")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
