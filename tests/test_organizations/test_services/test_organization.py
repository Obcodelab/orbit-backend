import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.exceptions import OrganizationHasProjectsError
from modules.organizations.repositories import organization_member_repository
from modules.organizations.services import organization_service
from modules.organizations.types import OrganizationRole
from modules.projects.services import project_service


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Service",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def test_create_organization_also_creates_owner_membership(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "svc-owner1@example.com")

    org = await organization_service.create_organization(
        db_session, name="Service Org", owner=owner
    )

    membership = await organization_member_repository.get_membership(
        db_session, org_id=org.id, user_id=owner.id
    )
    assert membership is not None
    assert membership.role == OrganizationRole.OWNER


async def test_list_for_user_includes_role_for_each_org(db_session: AsyncSession):
    user = await _make_user(db_session, "svc-owner2@example.com")
    other_owner = await _make_user(db_session, "svc-owner3@example.com")

    owned_org = await organization_service.create_organization(
        db_session, name="Owned Org", owner=user
    )
    joined_org = await organization_service.create_organization(
        db_session, name="Joined Org", owner=other_owner
    )
    await organization_member_repository.add_member(
        db_session, org_id=joined_org.id, user_id=user.id, role=OrganizationRole.MEMBER
    )

    page = await organization_service.list_for_user(
        db_session, user_id=user.id, limit=20, offset=0
    )

    by_name = {r.name: r.role for r in page.items}
    assert by_name[owned_org.name] == OrganizationRole.OWNER
    assert by_name[joined_org.name] == OrganizationRole.MEMBER


async def test_update_name_updates_org(db_session: AsyncSession):
    owner = await _make_user(db_session, "svc-owner4@example.com")
    org = await organization_service.create_organization(
        db_session, name="Before", owner=owner
    )

    updated = await organization_service.update_name(db_session, org=org, name="After")

    assert updated.name == "After"


async def test_delete_organization_raises_when_it_has_projects(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "svc-owner5@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    with pytest.raises(OrganizationHasProjectsError):
        await organization_service.delete_organization(db_session, org_id=org.id)


async def test_delete_organization_succeeds_when_empty(db_session: AsyncSession):
    owner = await _make_user(db_session, "svc-owner6@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    await organization_service.delete_organization(db_session, org_id=org.id)
