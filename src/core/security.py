import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from core.config import settings
from core.exceptions import TokenExpiredError, TokenInvalidError
from core.types import TokenType


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain a lowercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain a special character")
    return password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def _encode(
    claims: dict[str, Any], expires_delta: timedelta, token_type: TokenType
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    payload = {
        **claims,
        "type": token_type.value,
        "jti": str(uuid4()),
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token, expires_at


def create_access_token(claims: dict[str, Any]) -> tuple[str, datetime]:
    return _encode(
        claims,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        TokenType.ACCESS,
    )


def create_refresh_token(claims: dict[str, Any]) -> tuple[str, datetime]:
    return _encode(
        claims, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), TokenType.REFRESH
    )


def create_reset_token(claims: dict[str, Any]) -> tuple[str, datetime]:
    return _encode(
        claims,
        timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        TokenType.RESET,
    )


def create_token_pair(claims: dict[str, Any]) -> dict[str, Any]:
    """Access + refresh pair for sign-up/sign-in/OAuth."""
    access_token, access_expires_at = create_access_token(claims)
    refresh_token, _ = create_refresh_token(claims)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_at": access_expires_at,
    }


def decode_token(token: str) -> dict[str, Any]:
    """Full signature + expiry verification. Raises TokenExpiredError /
    TokenInvalidError rather than returning None, so callers can't forget
    to check a falsy result."""
    try:
        return jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError from exc
