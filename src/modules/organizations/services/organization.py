from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.organizations.models import Organization
from modules.organizations.repositories import (
    OrganizationMemberRepository,
    OrganizationRepository,
    organization_member_repository,
    organization_repository,
)
from modules.organizations.schemas import MyOrganizationResponse, OrganizationResponse
from modules.organizations.types import OrganizationRole


class OrganizationService:
    def __init__(
        self,
        org_repo: OrganizationRepository,
        member_repo: OrganizationMemberRepository,
    ) -> None:
        self.org_repo = org_repo
        self.member_repo = member_repo

    async def create_organization(
        self, session: AsyncSession, *, name: str, owner: User
    ) -> Organization:
        org = await self.org_repo.create_organization(
            session, name=name, owner_id=owner.id
        )
        await self.member_repo.add_member(
            session, org_id=org.id, user_id=owner.id, role=OrganizationRole.OWNER
        )
        return org

    async def list_for_user(
        self, session: AsyncSession, *, user_id: UUID
    ) -> list[MyOrganizationResponse]:
        memberships = await self.member_repo.get_for_user(session, user_id=user_id)
        return [
            MyOrganizationResponse(
                org_id=m.organization.id,
                name=m.organization.name,
                owner_id=m.organization.owner_id,
                role=m.role,
            )
            for m in memberships
        ]

    async def update_name(
        self, session: AsyncSession, *, org: Organization, name: str
    ) -> Organization:
        return await self.org_repo.update_name(session, org=org, name=name)

    async def delete_organization(self, session: AsyncSession, *, org_id: UUID) -> None:
        await self.org_repo.delete_by_id(session, org_id)

    def build_response(self, org: Organization) -> OrganizationResponse:
        return OrganizationResponse.model_validate(org)


organization_service = OrganizationService(
    org_repo=organization_repository, member_repo=organization_member_repository
)
