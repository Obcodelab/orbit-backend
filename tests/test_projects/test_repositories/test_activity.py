from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import activity_log_repository, project_repository
from modules.projects.types import ActivityAction


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_project(db_session: AsyncSession, owner_id) -> object:
    org = await organization_repository.create_organization(
        db_session, name="Test Org", owner_id=owner_id
    )
    return await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner_id,
    )


async def test_log_sets_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "arepo-owner1@example.com")
    project = await _make_project(db_session, owner.id)

    entry = await activity_log_repository.log(
        db_session,
        org_id=project.org_id,
        project_id=project.id,
        actor_id=owner.id,
        action=ActivityAction.TASK_CREATED,
        target="some-task-id",
    )

    assert entry.action == ActivityAction.TASK_CREATED
    assert entry.project_id == project.id


async def test_get_for_project_orders_newest_first(db_session: AsyncSession):
    owner = await _make_user(db_session, "arepo-owner2@example.com")
    project = await _make_project(db_session, owner.id)
    await activity_log_repository.log(
        db_session,
        org_id=project.org_id,
        project_id=project.id,
        actor_id=owner.id,
        action=ActivityAction.TASK_CREATED,
        target="a",
    )
    await activity_log_repository.log(
        db_session,
        org_id=project.org_id,
        project_id=project.id,
        actor_id=owner.id,
        action=ActivityAction.TASK_STATUS_CHANGED,
        target="a",
    )

    entries, total = await activity_log_repository.get_for_project(
        db_session, project_id=project.id, order=None, limit=20, offset=0
    )

    assert total == 2
    assert entries[0].action == ActivityAction.TASK_STATUS_CHANGED
    assert entries[1].action == ActivityAction.TASK_CREATED
