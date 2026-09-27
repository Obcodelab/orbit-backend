from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.services import organization_service
from modules.projects.services import activity_service, project_service
from modules.projects.types import ActivityAction
from modules.tasks.services import task_service
from modules.tasks.types import TaskPriority


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Service",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_project(db_session: AsyncSession, owner: User):
    org = await organization_service.create_organization(
        db_session, name="Test Org", owner=owner
    )
    return await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )


async def test_list_for_project_returns_logged_entries(db_session: AsyncSession):
    owner = await _make_user(db_session, "asvc-owner1@example.com")
    project = await _make_project(db_session, owner)
    await task_service.create_task(
        db_session,
        project=project,
        title="Task",
        description=None,
        assignee_ids=[],
        parent_task_id=None,
        priority=TaskPriority.MEDIUM,
        labels=None,
        due_date=None,
        creator_id=owner.id,
    )

    page = await activity_service.list_for_project(
        db_session, project_id=project.id, order=None, limit=20, offset=0
    )

    assert page.total == 1
    assert page.items[0].action == ActivityAction.TASK_CREATED
