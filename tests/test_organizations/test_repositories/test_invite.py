import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import (
    organization_invite_repository,
    organization_repository,
)
from modules.organizations.types import OrganizationRole


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_org(db_session: AsyncSession, owner_id) -> object:
    return await organization_repository.create_organization(
        db_session, name="Test Org", owner_id=owner_id
    )


async def test_create_invite_sets_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-owner1@example.com")
    org = await _make_org(db_session, owner.id)

    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email="invitee1@example.com",
        role=OrganizationRole.ADMIN,
        invited_by=owner.id,
    )

    assert invite.org_id == org.id
    assert invite.email == "invitee1@example.com"
    assert invite.role == OrganizationRole.ADMIN
    assert invite.invited_by == owner.id


async def test_create_invite_does_not_require_an_existing_account(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-owner2@example.com")
    org = await _make_org(db_session, owner.id)

    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email="never-registered@example.com",
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    assert invite.email == "never-registered@example.com"


async def test_create_invite_duplicate_raises_integrity_error(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-owner3@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email="invitee3@example.com",
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    with pytest.raises(IntegrityError):
        await organization_invite_repository.create_invite(
            db_session,
            org_id=org.id,
            email="invitee3@example.com",
            role=OrganizationRole.ADMIN,
            invited_by=owner.id,
        )
    await db_session.rollback()


async def test_get_invite_returns_none_when_no_pending_invite(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-owner4@example.com")
    org = await _make_org(db_session, owner.id)

    result = await organization_invite_repository.get_invite(
        db_session, org_id=org.id, email="stranger4@example.com"
    )

    assert result is None


async def test_get_by_id_with_org_eager_loads_organization(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-owner5@example.com")
    org = await _make_org(db_session, owner.id)
    invite = await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email="invitee5@example.com",
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    result = await organization_invite_repository.get_by_id_with_org(
        db_session, invite_id=invite.id
    )

    assert result is not None
    assert result.organization.name == "Test Org"


async def test_get_for_email_eager_loads_organization_and_inviter(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "inv-owner6@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email="invitee6@example.com",
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    invites = await organization_invite_repository.get_for_email(
        db_session, email="invitee6@example.com"
    )

    assert len(invites) == 1
    assert invites[0].organization.name == "Test Org"
    assert invites[0].inviter.email == "inv-owner6@example.com"


async def test_get_for_org_eager_loads_inviter(db_session: AsyncSession):
    owner = await _make_user(db_session, "inv-owner7@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_invite_repository.create_invite(
        db_session,
        org_id=org.id,
        email="invitee7@example.com",
        role=OrganizationRole.MEMBER,
        invited_by=owner.id,
    )

    invites = await organization_invite_repository.get_for_org(
        db_session, org_id=org.id
    )

    assert len(invites) == 1
    assert invites[0].email == "invitee7@example.com"
    assert invites[0].inviter.email == "inv-owner7@example.com"
