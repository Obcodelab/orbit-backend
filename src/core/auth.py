"""
Cross-cutting auth dependencies. Lives in core (not a module) because
every module needs "who is the caller" / "are they allowed here" without
importing another module's whole service layer. This is the one
deliberate exception to core never importing from modules.
"""

from collections.abc import Callable, Coroutine
from typing import Any
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
from modules.organizations.models import OrganizationMember
from modules.organizations.repositories import organization_member_repository
from modules.organizations.types import OrganizationRole

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


def require_role(
    *allowed_roles: OrganizationRole,
) -> Callable[..., Coroutine[Any, Any, OrganizationMember]]:
    """Org-scoped authorization for routes with an `{org_id}` path param.
    Returns the caller's membership row so handlers that also need the
    role don't have to look it up a second time."""

    async def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> OrganizationMember:
        forbidden = HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

        raw_org_id = request.path_params.get("org_id")
        if not raw_org_id:
            raise forbidden

        membership = await organization_member_repository.get_membership(
            session, org_id=UUID(raw_org_id), user_id=user.id
        )
        if not membership or membership.role not in allowed_roles:
            raise forbidden

        return membership

    return dependency
