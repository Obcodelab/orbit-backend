"""Central dependency imports for use in endpoint functions, e.g.
`async def get_me(user: AuthenticatedUser): ...`. `require_role` is
parametrized (`require_role(*allowed_roles)`), so it's re-exported as-is
here rather than as an `Annotated` constant — project-scoped roles are
added to it once the projects module exists."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, require_role
from core.database import get_session
from modules.auth.models import User

DBSession = Annotated[AsyncSession, Depends(get_session)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]

__all__ = ["DBSession", "AuthenticatedUser", "require_role"]
