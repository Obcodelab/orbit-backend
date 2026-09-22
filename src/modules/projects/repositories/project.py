from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from modules.projects.models import Project


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def create_project(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        key: str,
        name: str,
        description: str | None,
        owner_id: UUID,
    ) -> Project:
        return await self.create(
            session,
            org_id=org_id,
            key=key,
            name=name,
            description=description,
            owner_id=owner_id,
        )

    async def key_taken(self, session: AsyncSession, *, org_id: UUID, key: str) -> bool:
        existing = await self.get_by(session, org_id=org_id, key=key)
        return existing is not None

    async def update_fields(
        self, session: AsyncSession, *, project: Project, updates: dict
    ) -> Project:
        for field, value in updates.items():
            setattr(project, field, value)
        return await self.flush_and_refresh(session, project)


project_repository = ProjectRepository()
