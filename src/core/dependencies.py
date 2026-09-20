"""Central dependency imports for use in endpoint functions, e.g.
`async def get_me(user: AuthenticatedUser): ...`. `require_role`
(org/project-scoped authorization) is added here once the
organizations/projects modules exist."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.database import get_session
from modules.auth.models import User

DBSession = Annotated[AsyncSession, Depends(get_session)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]
