import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.exceptions import (
    CannotChangeOwnerRoleError,
    CannotRemoveOwnerError,
    MemberOwnsProjectsError,
    MembershipNotFoundError,
)
from modules.organizations.repositories import organization_member_repository
from modules.organizations.services import (
    organization_member_service,
    organization_service,
)
from modules.organizations.types import OrganizationRole
from modules.projects.repositories import project_member_repository
from modules.projects.services import project_member_service, project_service
from modules.projects.types import ProjectRole


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Service",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def test_get_member_raises_when_not_a_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "mem-owner1b@example.com")
    stranger = await _make_user(db_session, "mem-stranger1b@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    with pytest.raises(MembershipNotFoundError):
        await organization_member_service.get_member(
            db_session, org_id=org.id, user_id=stranger.id
        )


async def test_get_member_returns_response_with_user_details(db_session: AsyncSession):
    owner = await _make_user(db_session, "mem-owner2b@example.com")
    member = await _make_user(db_session, "mem-member2b@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.ADMIN
    )

    response = await organization_member_service.get_member(
        db_session, org_id=org.id, user_id=member.id
    )

    assert response.role == OrganizationRole.ADMIN
    assert response.user.email == member.email


async def test_remove_member_raises_when_not_a_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "mem-owner4@example.com")
    stranger = await _make_user(db_session, "mem-stranger4@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    with pytest.raises(MembershipNotFoundError):
        await organization_member_service.remove_member(
            db_session, org_id=org.id, user_id=stranger.id
        )


async def test_remove_member_raises_when_target_is_owner(db_session: AsyncSession):
    owner = await _make_user(db_session, "mem-owner5@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    with pytest.raises(CannotRemoveOwnerError):
        await organization_member_service.remove_member(
            db_session, org_id=org.id, user_id=owner.id
        )


async def test_update_role_raises_when_not_a_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "mem-owner6@example.com")
    stranger = await _make_user(db_session, "mem-stranger6@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    with pytest.raises(MembershipNotFoundError):
        await organization_member_service.update_role(
            db_session, org_id=org.id, user_id=stranger.id, role=OrganizationRole.ADMIN
        )


async def test_update_role_raises_when_target_is_owner(db_session: AsyncSession):
    owner = await _make_user(db_session, "mem-owner7@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )

    with pytest.raises(CannotChangeOwnerRoleError):
        await organization_member_service.update_role(
            db_session, org_id=org.id, user_id=owner.id, role=OrganizationRole.ADMIN
        )


async def test_remove_member_raises_when_they_own_a_project_in_the_org(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "mem-owner9@example.com")
    member = await _make_user(db_session, "mem-member9@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )
    await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=member,
    )

    with pytest.raises(MemberOwnsProjectsError):
        await organization_member_service.remove_member(
            db_session, org_id=org.id, user_id=member.id
        )


async def test_remove_member_cascades_to_their_project_memberships(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "mem-owner10@example.com")
    member = await _make_user(db_session, "mem-member10@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )
    await project_member_service.add_member(
        db_session, project=project, user_id=member.id, role=ProjectRole.MEMBER
    )

    await organization_member_service.remove_member(
        db_session, org_id=org.id, user_id=member.id
    )

    remaining = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=member.id
    )
    assert remaining is None


async def test_update_role_toggles_member_to_admin(db_session: AsyncSession):
    owner = await _make_user(db_session, "mem-owner8@example.com")
    member = await _make_user(db_session, "mem-member8@example.com")
    org = await organization_service.create_organization(
        db_session, name="Org", owner=owner
    )
    await organization_member_repository.add_member(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.MEMBER
    )

    response = await organization_member_service.update_role(
        db_session, org_id=org.id, user_id=member.id, role=OrganizationRole.ADMIN
    )

    assert response.role == OrganizationRole.ADMIN
