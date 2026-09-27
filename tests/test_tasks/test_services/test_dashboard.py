from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.services import organization_service
from modules.projects.repositories import project_member_repository
from modules.projects.services import project_service
from modules.tasks.services import dashboard_service, task_service
from modules.tasks.types import TaskPriority, TaskStatus


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


async def test_get_dashboard_computes_completion_percent(db_session: AsyncSession):
    owner = await _make_user(db_session, "dsvc-owner1@example.com")
    project = await _make_project(db_session, owner)
    task = await task_service.create_task(
        db_session,
        project=project,
        title="Task",
        description=None,
        assignee_ids=[owner.id],
        parent_task_id=None,
        priority=TaskPriority.MEDIUM,
        labels=None,
        due_date=None,
        creator_id=owner.id,
    )
    member_row = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=owner.id
    )
    await task_service.update_status(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        status=TaskStatus.DONE,
        caller=member_row,
    )

    dashboard = await dashboard_service.get_dashboard(db_session, project_id=project.id)

    assert dashboard.total_tasks == 1
    assert dashboard.completion_percent == 100.0


async def test_get_dashboard_zero_tasks_has_zero_completion(db_session: AsyncSession):
    owner = await _make_user(db_session, "dsvc-owner2@example.com")
    project = await _make_project(db_session, owner)

    dashboard = await dashboard_service.get_dashboard(db_session, project_id=project.id)

    assert dashboard.total_tasks == 0
    assert dashboard.completion_percent == 0.0
