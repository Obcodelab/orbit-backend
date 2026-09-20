from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from modules.organizations.models import OrganizationInvite
from modules.organizations.types import OrganizationRole


class OrganizationInviteRepository(BaseRepository[OrganizationInvite]):
    model = OrganizationInvite

    async def create_invite(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        email: str,
        role: OrganizationRole,
        invited_by: UUID | None,
    ) -> OrganizationInvite:
        return await self.create(
            session, org_id=org_id, email=email, role=role, invited_by=invited_by
        )

    async def get_invite(
        self, session: AsyncSession, *, org_id: UUID, email: str
    ) -> OrganizationInvite | None:
        return await self.get_by(session, org_id=org_id, email=email)

    async def get_by_id_with_org(
        self, session: AsyncSession, *, invite_id: UUID
    ) -> OrganizationInvite | None:
        stmt = (
            select(self.model)
            .where(self.model.id == invite_id)
            .options(selectinload(self.model.organization))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_email(
        self, session: AsyncSession, *, email: str
    ) -> list[OrganizationInvite]:
        stmt = (
            select(self.model)
            .where(self.model.email == email)
            .options(
                selectinload(self.model.organization), selectinload(self.model.inviter)
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_org(
        self, session: AsyncSession, *, org_id: UUID
    ) -> list[OrganizationInvite]:
        stmt = (
            select(self.model)
            .where(self.model.org_id == org_id)
            .options(selectinload(self.model.inviter))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


organization_invite_repository = OrganizationInviteRepository()
