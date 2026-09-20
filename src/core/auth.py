"""
Cross-cutting authentication dependency. Lives in core (not modules/auth)
because every module needs "who is the caller" without importing the
whole auth module's service layer. This is the one deliberate exception to
core never importing from modules.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.exceptions import TokenExpiredError, TokenInvalidError
from core.security import decode_token
from core.types import TokenType
from modules.auth.models import User
from modules.auth.repositories import blacklisted_token_repository, user_repository

_security = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    session: AsyncSession = Depends(get_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        claims = decode_token(credentials.credentials)
    except (TokenExpiredError, TokenInvalidError):
        raise unauthorized

    if claims.get("type") != TokenType.ACCESS:
        raise unauthorized

    raw_jti = claims.get("jti")
    if not raw_jti:
        raise unauthorized
    jti = UUID(raw_jti)

    if await blacklisted_token_repository.is_blacklisted(session, jti):
        raise unauthorized

    raw_user_id = claims.get("sub")
    user = (
        await user_repository.get_by_id(session, UUID(raw_user_id))
        if raw_user_id
        else None
    )
    if not user or not user.is_active:
        raise unauthorized

    # Stashed so the logout endpoint can blacklist this exact access token
    # without decoding it a second time.
    request.state.access_token = credentials.credentials
    request.state.access_jti = jti

    return user
