from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.email import send_email_mock
from modules.auth.models import User
from modules.auth.repositories import UserRepository, user_repository
from modules.organizations.exceptions import (
    AlreadyInvitedError,
    AlreadyMemberError,
    InviteNotFoundError,
)
from modules.organizations.repositories import (
    OrganizationInviteRepository,
    OrganizationMemberRepository,
    organization_invite_repository,
    organization_member_repository,
)
from modules.organizations.schemas import (
    MyInviteResponse,
    MyOrganizationResponse,
    OrgInviteResponse,
)
from modules.organizations.types import OrganizationRole


class OrganizationInviteService:
    def __init__(
        self,
        invite_repo: OrganizationInviteRepository,
        member_repo: OrganizationMemberRepository,
        user_repo: UserRepository,
    ) -> None:
        self.invite_repo = invite_repo
        self.member_repo = member_repo
        self.user_repo = user_repo

    async def create_invite(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        org_name: str,
        email: str,
        role: OrganizationRole,
        inviter: User,
    ) -> OrgInviteResponse:
        """No account required — the invite is keyed by email, so someone
        who hasn't registered yet can still be invited; it just sits there
        until they sign up (or log in, if they already have one)."""
        if await self.invite_repo.get_invite(session, org_id=org_id, email=email):
            raise AlreadyInvitedError

        existing_user = await self.user_repo.get_by_email(session, email)
        if existing_user and await self.member_repo.get_membership(
            session, org_id=org_id, user_id=existing_user.id
        ):
            raise AlreadyMemberError

        invite = await self.invite_repo.create_invite(
            session, org_id=org_id, email=email, role=role, invited_by=inviter.id
        )
        invite.inviter = inviter  # already have it — avoids a lazy-load on response

        body = (
            f"You've been invited to join {org_name} as {role}. Log in to accept "
            "or decline this invitation."
            if existing_user
            else f"You've been invited to join {org_name} as {role}. Register with "
            "this email to accept or decline this invitation."
        )
        send_email_mock(email, f"You've been invited to join {org_name}", body)
        return OrgInviteResponse.model_validate(invite)

    async def list_for_user(
        self, session: AsyncSession, *, email: str
    ) -> list[MyInviteResponse]:
        invites = await self.invite_repo.get_for_email(session, email=email)
        return [MyInviteResponse.model_validate(i) for i in invites]

    async def list_for_org(
        self, session: AsyncSession, *, org_id: UUID
    ) -> list[OrgInviteResponse]:
        invites = await self.invite_repo.get_for_org(session, org_id=org_id)
        return [OrgInviteResponse.model_validate(i) for i in invites]

    async def accept(
        self, session: AsyncSession, *, invite_id: UUID, user: User
    ) -> MyOrganizationResponse:
        invite = await self.invite_repo.get_by_id_with_org(session, invite_id=invite_id)
        if not invite or invite.email != user.email:
            raise InviteNotFoundError

        member = await self.member_repo.add_member(
            session, org_id=invite.org_id, user_id=user.id, role=invite.role
        )
        org = invite.organization
        await self.invite_repo.delete_by_id(session, invite_id)

        return MyOrganizationResponse(
            org_id=org.id, name=org.name, owner_id=org.owner_id, role=member.role
        )

    async def decline(
        self, session: AsyncSession, *, invite_id: UUID, user: User
    ) -> None:
        invite = await self.invite_repo.get_by_id(session, invite_id)
        if not invite or invite.email != user.email:
            raise InviteNotFoundError

        await self.invite_repo.delete_by_id(session, invite_id)

    async def revoke(
        self, session: AsyncSession, *, org_id: UUID, invite_id: UUID
    ) -> None:
        invite = await self.invite_repo.get_by_id(session, invite_id)
        if not invite or invite.org_id != org_id:
            raise InviteNotFoundError

        await self.invite_repo.delete_by_id(session, invite_id)


organization_invite_service = OrganizationInviteService(
    invite_repo=organization_invite_repository,
    member_repo=organization_member_repository,
    user_repo=user_repository,
)
