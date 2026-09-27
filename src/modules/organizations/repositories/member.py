from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from core.types import NameSort, SortOrder
from modules.auth.models import User
from modules.organizations.models import Organization, OrganizationMember
from modules.organizations.types import OrganizationRole

_ORG_SORT_COLUMNS = {
    NameSort.CREATED_AT: (OrganizationMember.created_at, SortOrder.DESC),
    NameSort.NAME: (Organization.name, SortOrder.ASC),
}


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
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        q: str | None,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationMember], int]:
        stmt = select(self.model).where(self.model.org_id == org_id)
        if q:
            stmt = stmt.join(User, User.id == self.model.user_id).where(
                or_(
                    User.email.ilike(f"%{q}%"),
                    User.first_name.ilike(f"%{q}%"),
                    User.last_name.ilike(f"%{q}%"),
                )
            )

        total = await self._count(session, stmt)
        stmt = self._apply_order(
            stmt,
            order=order,
            column=self.model.created_at,
            default_order=SortOrder.DESC,
        )
        stmt = stmt.options(selectinload(self.model.user)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        q: str | None,
        sort: NameSort | None,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationMember], int]:
        stmt = (
            select(self.model)
            .join(Organization, Organization.id == self.model.org_id)
            .where(self.model.user_id == user_id)
        )
        if q:
            stmt = stmt.where(Organization.name.ilike(f"%{q}%"))

        total = await self._count(session, stmt)
        stmt = self._apply_sort(
            stmt,
            sort=sort,
            order=order,
            columns=_ORG_SORT_COLUMNS,
            default_sort=NameSort.CREATED_AT,
        )
        stmt = (
            stmt.options(selectinload(self.model.organization))
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


organization_member_repository = OrganizationMemberRepository()
