from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.organizations.exceptions import (
    CannotChangeOwnerRoleError,
    CannotRemoveOwnerError,
    MembershipNotFoundError,
)
from modules.organizations.repositories import (
    OrganizationMemberRepository,
    organization_member_repository,
)
from modules.organizations.schemas import OrganizationMemberResponse
from modules.organizations.types import OrganizationRole


class OrganizationMemberService:
    def __init__(self, member_repo: OrganizationMemberRepository) -> None:
        self.member_repo = member_repo

    async def list_for_org(
        self, session: AsyncSession, *, org_id: UUID
    ) -> list[OrganizationMemberResponse]:
        members = await self.member_repo.get_for_org(session, org_id=org_id)
        return [OrganizationMemberResponse.model_validate(m) for m in members]

    async def get_member(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> OrganizationMemberResponse:
        membership = await self.member_repo.get_membership_with_user(
            session, org_id=org_id, user_id=user_id
        )
        if not membership:
            raise MembershipNotFoundError
        return OrganizationMemberResponse.model_validate(membership)

    async def remove_member(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> None:
        membership = await self.member_repo.get_membership(
            session, org_id=org_id, user_id=user_id
        )
        if not membership:
            raise MembershipNotFoundError
        if membership.role == OrganizationRole.OWNER:
            raise CannotRemoveOwnerError

        await self.member_repo.remove_member(session, org_id=org_id, user_id=user_id)

    async def update_role(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        user_id: UUID,
        role: OrganizationRole,
    ) -> OrganizationMemberResponse:
        membership = await self.member_repo.get_membership_with_user(
            session, org_id=org_id, user_id=user_id
        )
        if not membership:
            raise MembershipNotFoundError
        if membership.role == OrganizationRole.OWNER:
            raise CannotChangeOwnerRoleError

        user = membership.user  # keep a reference — avoids a lazy-load on response
        updated = await self.member_repo.update_role(
            session, member=membership, role=role
        )
        updated.user = user
        return OrganizationMemberResponse.model_validate(updated)


organization_member_service = OrganizationMemberService(
    member_repo=organization_member_repository
)
