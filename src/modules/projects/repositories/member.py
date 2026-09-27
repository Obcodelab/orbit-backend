from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from core.types import NameSort, SortOrder
from modules.auth.models import User
from modules.projects.models import Project, ProjectMember
from modules.projects.types import ProjectRole, ProjectStatus

_PROJECT_SORT_COLUMNS = {
    NameSort.CREATED_AT: (ProjectMember.created_at, SortOrder.DESC),
    NameSort.NAME: (Project.name, SortOrder.ASC),
}


class ProjectMemberRepository(BaseRepository[ProjectMember]):
    model = ProjectMember

    async def add_member(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> ProjectMember:
        return await self.create(
            session, project_id=project_id, user_id=user_id, role=role
        )

    async def get_membership(
        self, session: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> ProjectMember | None:
        return await self.get_by(session, project_id=project_id, user_id=user_id)

    async def get_membership_with_user(
        self, session: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> ProjectMember | None:
        stmt = (
            select(self.model)
            .where(self.model.project_id == project_id, self.model.user_id == user_id)
            .options(selectinload(self.model.user))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def remove_member(
        self, session: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> None:
        await self.delete_by(session, project_id=project_id, user_id=user_id)

    async def remove_for_org(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> None:
        """Removes a user's membership from every project in one org —
        one query instead of looping over each project."""
        project_ids = select(Project.id).where(Project.org_id == org_id)
        stmt = delete(self.model).where(
            self.model.user_id == user_id, self.model.project_id.in_(project_ids)
        )
        await session.execute(stmt)

    async def get_member_user_ids(
        self, session: AsyncSession, *, project_id: UUID, user_ids: list[UUID]
    ) -> set[UUID]:
        """Which of `user_ids` are actually members of this project — one
        query for the whole batch instead of one per id."""
        stmt = select(self.model.user_id).where(
            self.model.project_id == project_id, self.model.user_id.in_(user_ids)
        )
        result = await session.execute(stmt)
        return set(result.scalars().all())

    async def update_role(
        self, session: AsyncSession, *, member: ProjectMember, role: ProjectRole
    ) -> ProjectMember:
        member.role = role
        return await self.flush_and_refresh(session, member)

    async def get_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        q: str | None,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ProjectMember], int]:
        stmt = select(self.model).where(self.model.project_id == project_id)
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
        status_filter: ProjectStatus | None,
        q: str | None,
        sort: NameSort | None,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ProjectMember], int]:
        """Status filtering happens here, not in Python after fetching —
        it has to run before LIMIT/OFFSET or pagination and the archived
        default both come out wrong."""
        stmt = (
            select(self.model)
            .join(Project, self.model.project_id == Project.id)
            .where(self.model.user_id == user_id)
        )
        stmt = stmt.where(
            Project.status == status_filter
            if status_filter
            else Project.status != ProjectStatus.ARCHIVED
        )
        if q:
            stmt = stmt.where(Project.name.ilike(f"%{q}%"))

        total = await self._count(session, stmt)
        stmt = self._apply_sort(
            stmt,
            sort=sort,
            order=order,
            columns=_PROJECT_SORT_COLUMNS,
            default_sort=NameSort.CREATED_AT,
        )
        stmt = (
            stmt.options(selectinload(self.model.project)).limit(limit).offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


project_member_repository = ProjectMemberRepository()
