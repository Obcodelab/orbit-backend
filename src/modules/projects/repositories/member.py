from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from modules.projects.models import Project, ProjectMember
from modules.projects.types import ProjectRole, ProjectStatus


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

    async def update_role(
        self, session: AsyncSession, *, member: ProjectMember, role: ProjectRole
    ) -> ProjectMember:
        member.role = role
        return await self.flush_and_refresh(session, member)

    async def get_for_project(
        self, session: AsyncSession, *, project_id: UUID, limit: int, offset: int
    ) -> tuple[list[ProjectMember], int]:
        stmt = select(self.model).where(self.model.project_id == project_id)
        total = await self._count(session, stmt)
        stmt = stmt.options(selectinload(self.model.user)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        status_filter: ProjectStatus | None,
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
        total = await self._count(session, stmt)
        stmt = (
            stmt.options(selectinload(self.model.project)).limit(limit).offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


project_member_repository = ProjectMemberRepository()
