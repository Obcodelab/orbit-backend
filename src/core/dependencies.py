"""Central dependency imports for use in endpoint functions, e.g.
`async def get_me(user: AuthenticatedUser): ...`. `require_role` and
`require_project_role` are parametrized (`require_role(*allowed_roles)`),
so they're re-exported as-is here rather than as `Annotated` constants."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, require_project_role, require_role
from core.database import get_session
from core.pagination import Pagination, pagination_params
from modules.auth.models import User

DBSession = Annotated[AsyncSession, Depends(get_session)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]
PaginationParams = Annotated[Pagination, Depends(pagination_params)]

__all__ = [
    "DBSession",
    "AuthenticatedUser",
    "PaginationParams",
    "require_role",
    "require_project_role",
]
