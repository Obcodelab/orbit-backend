from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_repository
from modules.projects.types import ProjectStatus


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


async def test_create_project_sets_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "proj-owner1@example.com")
    org = await _make_org(db_session, owner.id)

    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description="The main project",
        owner_id=owner.id,
    )

    assert project.org_id == org.id
    assert project.key == "ORB"
    assert project.name == "Orbit"
    assert project.status == ProjectStatus.ACTIVE
    assert project.task_counter == 0


async def test_key_taken_true_when_key_exists_in_org(db_session: AsyncSession):
    owner = await _make_user(db_session, "proj-owner2@example.com")
    org = await _make_org(db_session, owner.id)
    await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner.id,
    )

    assert await project_repository.key_taken(db_session, org_id=org.id, key="ORB")
    assert not await project_repository.key_taken(
        db_session, org_id=org.id, key="OTHER"
    )


async def test_key_taken_false_for_same_key_in_different_org(db_session: AsyncSession):
    owner = await _make_user(db_session, "proj-owner3@example.com")
    org_a = await _make_org(db_session, owner.id)
    org_b = await _make_org(db_session, owner.id)
    await project_repository.create_project(
        db_session,
        org_id=org_a.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner.id,
    )

    assert not await project_repository.key_taken(
        db_session, org_id=org_b.id, key="ORB"
    )


async def test_update_fields_persists_changes(db_session: AsyncSession):
    owner = await _make_user(db_session, "proj-owner4@example.com")
    org = await _make_org(db_session, owner.id)
    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Old Name",
        description=None,
        owner_id=owner.id,
    )

    updated = await project_repository.update_fields(
        db_session, project=project, updates={"name": "New Name"}
    )

    assert updated.name == "New Name"
