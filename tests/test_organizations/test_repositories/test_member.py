import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import (
    organization_member_repository,
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


async def test_add_member_creates_row(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner@example.com")
    member = await _make_user(db_session, "member@example.com")
    org = await _make_org(db_session, owner.id)

    row = await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )

    assert row.org_id == org.id
    assert row.user_id == member.id
    assert row.role == OrganizationRole.MEMBER


async def test_add_member_duplicate_raises_integrity_error(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner2@example.com")
    member = await _make_user(db_session, "member2@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )

    with pytest.raises(IntegrityError):
        await organization_member_repository.add_member(
            db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.ADMIN
        )
    await db_session.rollback()


async def test_get_membership_returns_none_when_not_a_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner3@example.com")
    stranger = await _make_user(db_session, "stranger3@example.com")
    org = await _make_org(db_session, owner.id)

    result = await organization_member_repository.get_membership(
        db_session, org_id=org.id, user_id=stranger.id
    )

    assert result is None


async def test_get_membership_with_user_eager_loads_user(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner4@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=owner.id, role=OrganizationRole.OWNER
    )

    result = await organization_member_repository.get_membership_with_user(
        db_session, org_id=org.id, user_id=owner.id
    )

    assert result is not None
    assert result.user.email == "owner4@example.com"


async def test_get_for_org_eager_loads_user_for_each_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner5@example.com")
    member = await _make_user(db_session, "member5@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=owner.id, role=OrganizationRole.OWNER
    )
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )

    members, total = await organization_member_repository.get_for_org(
        db_session, org_id=org.id, limit=20, offset=0
    )

    assert total == 2
    emails = {m.user.email for m in members}
    assert emails == {"owner5@example.com", "member5@example.com"}


async def test_get_for_user_eager_loads_organization(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner6@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=owner.id, role=OrganizationRole.OWNER
    )

    memberships, total = await organization_member_repository.get_for_user(
        db_session, user_id=owner.id, limit=20, offset=0
    )

    assert total == 1
    assert len(memberships) == 1
    assert memberships[0].organization.name == "Test Org"


async def test_remove_member_deletes_row(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner7@example.com")
    member = await _make_user(db_session, "member7@example.com")
    org = await _make_org(db_session, owner.id)
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )

    await organization_member_repository.remove_member(
        db_session, org_id=org.id, user_id=member.id
    )

    result = await organization_member_repository.get_membership(
        db_session, org_id=org.id, user_id=member.id
    )
    assert result is None


async def test_update_role_persists_new_role(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner8@example.com")
    member = await _make_user(db_session, "member8@example.com")
    org = await _make_org(db_session, owner.id)
    row = await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )

    updated = await organization_member_repository.update_role(
        db_session, member=row, role=OrganizationRole.ADMIN
    )

    assert updated.role == OrganizationRole.ADMIN
