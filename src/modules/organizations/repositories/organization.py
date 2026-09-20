from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from modules.organizations.models import Organization


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    async def create_organization(
        self, session: AsyncSession, *, name: str, owner_id: UUID
    ) -> Organization:
        return await self.create(session, name=name, owner_id=owner_id)

    async def update_name(
        self, session: AsyncSession, *, org: Organization, name: str
    ) -> Organization:
        org.name = name
        return await self.flush_and_refresh(session, org)


organization_repository = OrganizationRepository()
