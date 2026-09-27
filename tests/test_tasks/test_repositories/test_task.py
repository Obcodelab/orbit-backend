from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_repository
from modules.tasks.repositories import task_assignee_repository, task_repository
from modules.tasks.types import TaskPriority, TaskStatus


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


async def _make_task(
    db_session: AsyncSession, project, owner_id, number=1, **overrides
):
    defaults = dict(
        org_id=project.org_id,
        project_id=project.id,
        number=number,
        parent_task_id=None,
        title="Fix bug",
        description=None,
        priority=TaskPriority.MEDIUM,
        labels=None,
        due_date=None,
        created_by=owner_id,
    )
    defaults.update(overrides)
    return await task_repository.create_task(db_session, **defaults)


async def test_create_task_sets_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner1@example.com")
    project = await _make_project(db_session, owner.id)

    task = await _make_task(
        db_session, project, owner.id, title="Fix bug", description="It's broken"
    )

    assert task.project_id == project.id
    assert task.org_id == project.org_id
    assert task.number == 1
    assert task.title == "Fix bug"
    assert task.status == TaskStatus.TODO
    assert task.priority == TaskPriority.MEDIUM


async def test_get_scoped_returns_none_for_wrong_project(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner2@example.com")
    project_a = await _make_project(db_session, owner.id)
    other_owner = await _make_user(db_session, "trepo-owner2b@example.com")
    project_b = await _make_project(db_session, other_owner.id)
    task = await _make_task(db_session, project_a, owner.id)

    result = await task_repository.get_scoped(
        db_session, project_id=project_b.id, task_id=task.id
    )

    assert result is None


async def test_get_scoped_with_assignees_eager_loads_user_and_project(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "trepo-owner3@example.com")
    project = await _make_project(db_session, owner.id)
    task = await _make_task(db_session, project, owner.id)
    await task_assignee_repository.assign_many(
        db_session, task_id=task.id, user_ids=[owner.id]
    )

    result = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project.id, task_id=task.id
    )

    assert result is not None
    assert result.assignees[0].user.email == "trepo-owner3@example.com"
    assert result.project.key == "ORB"


async def test_update_fields_persists_changes(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner4@example.com")
    project = await _make_project(db_session, owner.id)
    task = await _make_task(db_session, project, owner.id)

    updated = await task_repository.update_fields(
        db_session, task=task, updates={"title": "Renamed"}
    )

    assert updated.title == "Renamed"


async def test_get_for_project_filters_by_status(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner5@example.com")
    project = await _make_project(db_session, owner.id)
    todo = await _make_task(db_session, project, owner.id, number=1, title="Todo task")
    done = await _make_task(db_session, project, owner.id, number=2, title="Done task")
    await task_repository.update_fields(
        db_session, task=done, updates={"status": TaskStatus.DONE}
    )

    tasks, total = await task_repository.get_for_project(
        db_session,
        project_id=project.id,
        status_filter=TaskStatus.TODO,
        priority_filter=None,
        assignee_id=None,
        label=None,
        parent_id=None,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert tasks[0].id == todo.id


async def test_get_for_project_filters_by_assignee(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner6@example.com")
    other = await _make_user(db_session, "trepo-other6@example.com")
    project = await _make_project(db_session, owner.id)
    assigned = await _make_task(
        db_session, project, owner.id, number=1, title="Assigned"
    )
    await _make_task(db_session, project, owner.id, number=2, title="Unassigned")
    await task_assignee_repository.assign_many(
        db_session, task_id=assigned.id, user_ids=[other.id]
    )

    tasks, total = await task_repository.get_for_project(
        db_session,
        project_id=project.id,
        status_filter=None,
        priority_filter=None,
        assignee_id=other.id,
        label=None,
        parent_id=None,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert tasks[0].id == assigned.id


async def test_get_for_project_filters_by_label(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner7@example.com")
    project = await _make_project(db_session, owner.id)
    bug = await _make_task(
        db_session, project, owner.id, number=1, title="Bug", labels="bug,urgent"
    )
    await _make_task(
        db_session, project, owner.id, number=2, title="Feature", labels="feature"
    )

    tasks, total = await task_repository.get_for_project(
        db_session,
        project_id=project.id,
        status_filter=None,
        priority_filter=None,
        assignee_id=None,
        label="urgent",
        parent_id=None,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert tasks[0].id == bug.id


async def test_get_for_project_filters_by_parent_id(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner8@example.com")
    project = await _make_project(db_session, owner.id)
    parent = await _make_task(db_session, project, owner.id, number=1, title="Parent")
    child = await _make_task(
        db_session,
        project,
        owner.id,
        number=2,
        title="Child",
        parent_task_id=parent.id,
    )

    tasks, total = await task_repository.get_for_project(
        db_session,
        project_id=project.id,
        status_filter=None,
        priority_filter=None,
        assignee_id=None,
        label=None,
        parent_id=parent.id,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert tasks[0].id == child.id


async def test_get_for_project_filters_by_priority(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner10@example.com")
    project = await _make_project(db_session, owner.id)
    urgent = await _make_task(
        db_session,
        project,
        owner.id,
        number=1,
        title="Urgent",
        priority=TaskPriority.HIGH,
    )
    await _make_task(
        db_session,
        project,
        owner.id,
        number=2,
        title="Later",
        priority=TaskPriority.LOW,
    )

    tasks, total = await task_repository.get_for_project(
        db_session,
        project_id=project.id,
        status_filter=None,
        priority_filter=TaskPriority.HIGH,
        assignee_id=None,
        label=None,
        parent_id=None,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert tasks[0].id == urgent.id


async def test_get_for_project_default_sort_is_newest_first(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner11@example.com")
    project = await _make_project(db_session, owner.id)
    first = await _make_task(db_session, project, owner.id, number=1, title="First")
    second = await _make_task(db_session, project, owner.id, number=2, title="Second")

    tasks, _ = await task_repository.get_for_project(
        db_session,
        project_id=project.id,
        status_filter=None,
        priority_filter=None,
        assignee_id=None,
        label=None,
        parent_id=None,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert [t.id for t in tasks] == [second.id, first.id]


async def test_count_by_status_groups_correctly(db_session: AsyncSession):
    owner = await _make_user(db_session, "trepo-owner9@example.com")
    project = await _make_project(db_session, owner.id)
    todo_task = await _make_task(db_session, project, owner.id, number=1)
    done_task = await _make_task(db_session, project, owner.id, number=2)
    await task_repository.update_fields(
        db_session, task=done_task, updates={"status": TaskStatus.DONE}
    )

    counts = await task_repository.count_by_status(db_session, project_id=project.id)

    assert counts[TaskStatus.TODO] == 1
    assert counts[TaskStatus.DONE] == 1
    assert todo_task.status == TaskStatus.TODO
