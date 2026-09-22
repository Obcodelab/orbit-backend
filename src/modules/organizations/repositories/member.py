from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from modules.organizations.models import OrganizationMember
from modules.organizations.types import OrganizationRole


class OrganizationMemberRepository(BaseRepository[OrganizationMember]):
    model = OrganizationMember

    async def add_member(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        user_id: UUID,
        role: OrganizationRole,
    ) -> OrganizationMember:
        return await self.create(session, org_id=org_id, user_id=user_id, role=role)

    async def get_membership(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> OrganizationMember | None:
        return await self.get_by(session, org_id=org_id, user_id=user_id)

    async def get_membership_with_user(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> OrganizationMember | None:
        stmt = (
            select(self.model)
            .where(self.model.org_id == org_id, self.model.user_id == user_id)
            .options(selectinload(self.model.user))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def remove_member(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> None:
        await self.delete_by(session, org_id=org_id, user_id=user_id)

    async def update_role(
        self,
        session: AsyncSession,
        *,
        member: OrganizationMember,
        role: OrganizationRole,
    ) -> OrganizationMember:
        member.role = role
        return await self.flush_and_refresh(session, member)

    async def get_for_org(
        self, session: AsyncSession, *, org_id: UUID, limit: int, offset: int
    ) -> tuple[list[OrganizationMember], int]:
        stmt = select(self.model).where(self.model.org_id == org_id)
        total = await self._count(session, stmt)
        stmt = stmt.options(selectinload(self.model.user)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_for_user(
        self, session: AsyncSession, *, user_id: UUID, limit: int, offset: int
    ) -> tuple[list[OrganizationMember], int]:
        stmt = select(self.model).where(self.model.user_id == user_id)
        total = await self._count(session, stmt)
        stmt = (
            stmt.options(selectinload(self.model.organization))
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


organization_member_repository = OrganizationMemberRepository()
