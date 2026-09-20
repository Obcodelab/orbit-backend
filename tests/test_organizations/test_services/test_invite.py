import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.exceptions import (
    AlreadyInvitedError,
    AlreadyMemberError,
    InviteNotFoundError,
)
from modules.organizations.repositories import (
    organization_invite_repository,
    organization_member_repository,
)
from modules.organizations.services import (
    organization_invite_service,
    organization_service,
)
from modules.organizations.types import OrganizationRole


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Service",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def test_create_invite_does_not_require_an_existing_account(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-svc-owner1@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    response = await organization_invite_service.create_invite(
        db_session,
        org_id=org.id,
        org_name=org.name,
        email="never-registered@example.com",
        role=OrganizationRole.MEMBER,
        inviter=owner,
    )

    assert response.email == "never-registered@example.com"


async def test_create_invite_raises_when_already_a_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-svc-owner2@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    with pytest.raises(AlreadyMemberError):
        await organization_invite_service.create_invite(
            db_session,
            org_id=org.id,
            org_name=org.name,
            email=owner.email,
            role=OrganizationRole.MEMBER,
            inviter=owner,
        )


async def test_create_invite_raises_when_already_invited(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-svc-owner3@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    await organization_invite_service.create_invite(
        db_session,
        org_id=org.id,
        org_name=org.name,
        email="invitee3@example.com",
        role=OrganizationRole.MEMBER,
        inviter=owner,
    )

    with pytest.raises(AlreadyInvitedError):
        await organization_invite_service.create_invite(
            db_session,
            org_id=org.id,
            org_name=org.name,
            email="invitee3@example.com",
            role=OrganizationRole.ADMIN,
            inviter=owner,
        )


async def test_create_invite_success_returns_response_with_details(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-svc-owner4@example.com")
    invitee = await _make_user(db_session, "inv-svc-invitee4@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    response = await organization_invite_service.create_invite(
        db_session,
        org_id=org.id,
        org_name=org.name,
        email=invitee.email,
        role=OrganizationRole.ADMIN,
        inviter=owner,
    )

    assert response.role == OrganizationRole.ADMIN
    assert response.email == invitee.email
    assert response.inviter is not None
    assert response.inviter.user_id == owner.id


async def test_accept_creates_membership_and_deletes_invite(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-svc-owner5@example.com")
    invitee = await _make_user(db_session, "inv-svc-invitee5@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email=invitee.email,
        role=OrganizationRole.ADMIN,
        invited_by=owner.id,
    )

    result = await organization_invite_service.accept(
        db_session, invite_id=invite.id, user=invitee
    )

    assert result.org_id == org.id
    assert result.role == OrganizationRole.ADMIN

    membership = await organization_member_repository.get_membership(
        db_session, org_id=org.id, user_id=invitee.id
    )
    assert membership is not None
    assert membership.role == OrganizationRole.ADMIN

    remaining = await organization_invite_repository.get_by_id(db_session, invite.id)
    assert remaining is None


async def test_accept_raises_when_invite_belongs_to_someone_else(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-svc-owner6@example.com")
    invitee = await _make_user(db_session, "inv-svc-invitee6@example.com")
    stranger = await _make_user(db_session, "inv-svc-stranger6@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email=invitee.email,
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    with pytest.raises(InviteNotFoundError):
        await organization_invite_service.accept(
            db_session, invite_id=invite.id, user=stranger
        )


async def test_decline_deletes_invite_without_creating_membership(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-svc-owner7@example.com")
    invitee = await _make_user(db_session, "inv-svc-invitee7@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email=invitee.email,
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    await organization_invite_service.decline(
        db_session, invite_id=invite.id, user=invitee
    )

    remaining = await organization_invite_repository.get_by_id(db_session, invite.id)
    assert remaining is None
    membership = await organization_member_repository.get_membership(
        db_session, org_id=org.id, user_id=invitee.id
    )
    assert membership is None


async def test_decline_raises_when_invite_belongs_to_someone_else(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-svc-owner8@example.com")
    invitee = await _make_user(db_session, "inv-svc-invitee8@example.com")
    stranger = await _make_user(db_session, "inv-svc-stranger8@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email=invitee.email,
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    with pytest.raises(InviteNotFoundError):
        await organization_invite_service.decline(
            db_session, invite_id=invite.id, user=stranger
        )


async def test_revoke_deletes_invite(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-svc-owner9@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email="invitee9@example.com",
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    await organization_invite_service.revoke(
        db_session, org_id=org.id, invite_id=invite.id
    )

    remaining = await organization_invite_repository.get_by_id(db_session, invite.id)
    assert remaining is None


async def test_revoke_raises_when_invite_belongs_to_different_org(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-svc-owner10@example.com")
    org_a = await organization_service.create_organization(
        db_session, name="Org A", owner=owner
    )
    org_b = await organization_service.create_organization(
        db_session, name="Org B", owner=owner
    )
    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org_a.id,
        email="invitee10@example.com",
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    with pytest.raises(InviteNotFoundError):
        await organization_invite_service.revoke(
            db_session, org_id=org_b.id, invite_id=invite.id
        )
