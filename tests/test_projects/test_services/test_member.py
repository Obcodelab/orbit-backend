import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_member_repository
from modules.organizations.services import organization_service
from modules.organizations.types import OrganizationRole
from modules.projects.exceptions import (
    AlreadyProjectMemberError,
    CannotChangeProjectOwnerRoleError,
    CannotRemoveProjectOwnerError,
    NotOrgMemberError,
    ProjectArchivedError,
    ProjectMembershipNotFoundError,
)
from modules.projects.repositories import project_repository
from modules.projects.services import project_member_service, project_service
from modules.projects.types import ProjectRole, ProjectStatus


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Service",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_org(db_session: AsyncSession, owner: User) -> object:
    """Goes through the org service, not the repository directly, so the
    owner actually gets an OrganizationMember row — matching how orgs are
    really created and needed by tests that check org-membership state."""
    return await organization_service.create_organization(
        db_session, name="Test Org", owner=owner
    )


async def test_add_member_raises_when_not_an_org_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner1@example.com")
    stranger = await _make_user(db_session, "pmsvc-stranger1@example.com")
    org = await _make_org(db_session, owner)
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    with pytest.raises(NotOrgMemberError):
        await project_member_service.add_member(
            db_session, project=project, user_id=stranger.id, role=ProjectRole.MEMBER
        )


async def test_add_member_succeeds_for_org_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner2@example.com")
    member = await _make_user(db_session, "pmsvc-member2@example.com")
    org = await _make_org(db_session, owner)
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

    response = await project_member_service.add_member(
        db_session, project=project, user_id=member.id, role=ProjectRole.ADMIN
    )

    assert response.role == ProjectRole.ADMIN
    assert response.user.email == member.email


async def test_add_member_raises_when_already_a_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner3@example.com")
    org = await _make_org(db_session, owner)
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    with pytest.raises(AlreadyProjectMemberError):
        await project_member_service.add_member(
            db_session, project=project, user_id=owner.id, role=ProjectRole.MEMBER
        )


async def test_add_member_raises_when_project_archived(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner4@example.com")
    member = await _make_user(db_session, "pmsvc-member4@example.com")
    org = await _make_org(db_session, owner)
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
    project = await project_repository.update_fields(
        db_session, project=project, updates={"status": ProjectStatus.ARCHIVED}
    )

    with pytest.raises(ProjectArchivedError):
        await project_member_service.add_member(
            db_session, project=project, user_id=member.id, role=ProjectRole.MEMBER
        )


async def test_remove_member_raises_when_target_is_owner(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner5@example.com")
    org = await _make_org(db_session, owner)
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    with pytest.raises(CannotRemoveProjectOwnerError):
        await project_member_service.remove_member(
            db_session, project_id=project.id, user_id=owner.id
        )


async def test_remove_member_raises_when_not_a_member(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner6@example.com")
    stranger = await _make_user(db_session, "pmsvc-stranger6@example.com")
    org = await _make_org(db_session, owner)
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    with pytest.raises(ProjectMembershipNotFoundError):
        await project_member_service.remove_member(
            db_session, project_id=project.id, user_id=stranger.id
        )


async def test_update_role_raises_when_target_is_owner(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner7@example.com")
    org = await _make_org(db_session, owner)
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    with pytest.raises(CannotChangeProjectOwnerRoleError):
        await project_member_service.update_role(
            db_session, project_id=project.id, user_id=owner.id, role=ProjectRole.ADMIN
        )


async def test_update_role_toggles_member_to_admin(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmsvc-owner8@example.com")
    member = await _make_user(db_session, "pmsvc-member8@example.com")
    org = await _make_org(db_session, owner)
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

    response = await project_member_service.update_role(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.ADMIN
    )

    assert response.role == ProjectRole.ADMIN
