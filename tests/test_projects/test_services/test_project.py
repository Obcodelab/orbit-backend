import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.exceptions import DuplicateProjectKeyError
from modules.projects.repositories import project_member_repository, project_repository
from modules.projects.services import project_service
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


async def _make_org(db_session: AsyncSession, owner_id) -> object:
    return await organization_repository.create_organization(
        db_session, name="Test Org", owner_id=owner_id
    )


async def test_create_project_also_creates_owner_membership(db_session: AsyncSession):
    owner = await _make_user(db_session, "psvc-owner1@example.com")
    org = await _make_org(db_session, owner.id)

    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    membership = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=owner.id
    )
    assert membership is not None
    assert membership.role == ProjectRole.OWNER


async def test_create_project_raises_on_duplicate_key(db_session: AsyncSession):
    owner = await _make_user(db_session, "psvc-owner2@example.com")
    org = await _make_org(db_session, owner.id)
    await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )

    with pytest.raises(DuplicateProjectKeyError):
        await project_service.create_project(
            db_session,
            org_id=org.id,
            key="ORB",
            name="Orbit 2",
            description=None,
            owner=owner,
        )


async def test_list_for_user_excludes_archived_by_default(db_session: AsyncSession):
    owner = await _make_user(db_session, "psvc-owner3@example.com")
    org = await _make_org(db_session, owner.id)
    await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ACT",
        name="Active",
        description=None,
        owner=owner,
    )
    archived = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ARC",
        name="Archived",
        description=None,
        owner=owner,
    )
    await project_service.update_project(
        db_session, project=archived, updates={"status": ProjectStatus.ARCHIVED}
    )

    page = await project_service.list_for_user(
        db_session, user_id=owner.id, status_filter=None, limit=20, offset=0
    )

    names = {r.name for r in page.items}
    assert names == {"Active"}


async def test_list_for_user_status_filter_shows_only_that_status(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "psvc-owner4@example.com")
    org = await _make_org(db_session, owner.id)
    archived = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ARC",
        name="Archived",
        description=None,
        owner=owner,
    )
    await project_service.update_project(
        db_session, project=archived, updates={"status": ProjectStatus.ARCHIVED}
    )
    await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ACT",
        name="Active",
        description=None,
        owner=owner,
    )

    page = await project_service.list_for_user(
        db_session,
        user_id=owner.id,
        status_filter=ProjectStatus.ARCHIVED,
        limit=20,
        offset=0,
    )

    names = {r.name for r in page.items}
    assert names == {"Archived"}


async def test_update_project_updates_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "psvc-owner5@example.com")
    org = await _make_org(db_session, owner.id)
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Before",
        description=None,
        owner=owner,
    )

    updated = await project_service.update_project(
        db_session, project=project, updates={"name": "After"}
    )

    assert updated.name == "After"


async def test_delete_project_frees_up_its_key(db_session: AsyncSession):
    owner = await _make_user(db_session, "psvc-owner6@example.com")
    org = await _make_org(db_session, owner.id)
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="TYP",
        name="Typo'd",
        description=None,
        owner=owner,
    )

    await project_service.delete_project(db_session, project_id=project.id)

    assert not await project_repository.key_taken(db_session, org_id=org.id, key="TYP")
