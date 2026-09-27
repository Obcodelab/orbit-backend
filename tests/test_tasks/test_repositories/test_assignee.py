import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_repository
from modules.tasks.repositories import task_assignee_repository, task_repository
from modules.tasks.types import TaskPriority


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_task(db_session: AsyncSession, project, owner_id, number=1):
    return await task_repository.create_task(
        db_session,
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


async def test_assign_many_creates_rows(db_session: AsyncSession):
    owner = await _make_user(db_session, "tarepo-owner1@example.com")
    member = await _make_user(db_session, "tarepo-member1@example.com")
    org = await organization_repository.create_organization(
        db_session, name="Org", owner_id=owner.id
    )
    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner.id,
    )
    task = await _make_task(db_session, project, owner.id)

    await task_assignee_repository.assign_many(
        db_session, task_id=task.id, user_ids=[owner.id, member.id]
    )

    task_with_assignees = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project.id, task_id=task.id
    )
    assert {a.user_id for a in task_with_assignees.assignees} == {owner.id, member.id}


async def test_assign_many_empty_list_is_a_noop(db_session: AsyncSession):
    owner = await _make_user(db_session, "tarepo-owner2@example.com")
    org = await organization_repository.create_organization(
        db_session, name="Org", owner_id=owner.id
    )
    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner.id,
    )
    task = await _make_task(db_session, project, owner.id)

    await task_assignee_repository.assign_many(db_session, task_id=task.id, user_ids=[])

    task_with_assignees = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project.id, task_id=task.id
    )
    assert task_with_assignees.assignees == []


async def test_assign_many_duplicate_raises_integrity_error(db_session: AsyncSession):
    owner = await _make_user(db_session, "tarepo-owner3@example.com")
    org = await organization_repository.create_organization(
        db_session, name="Org", owner_id=owner.id
    )
    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner.id,
    )
    task = await _make_task(db_session, project, owner.id)
    await task_assignee_repository.assign_many(
        db_session, task_id=task.id, user_ids=[owner.id]
    )

    with pytest.raises(IntegrityError):
        await task_assignee_repository.assign_many(
            db_session, task_id=task.id, user_ids=[owner.id]
        )
    await db_session.rollback()


async def test_replace_all_swaps_assignees(db_session: AsyncSession):
    owner = await _make_user(db_session, "tarepo-owner4@example.com")
    member = await _make_user(db_session, "tarepo-member4@example.com")
    org = await organization_repository.create_organization(
        db_session, name="Org", owner_id=owner.id
    )
    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner.id,
    )
    task = await _make_task(db_session, project, owner.id)
    await task_assignee_repository.assign_many(
        db_session, task_id=task.id, user_ids=[owner.id]
    )

    await task_assignee_repository.replace_all(
        db_session, task_id=task.id, user_ids=[member.id]
    )

    task_with_assignees = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project.id, task_id=task.id
    )
    assert {a.user_id for a in task_with_assignees.assignees} == {member.id}


async def test_remove_for_project_only_affects_that_project(db_session: AsyncSession):
    owner = await _make_user(db_session, "tarepo-owner5@example.com")
    org = await organization_repository.create_organization(
        db_session, name="Org", owner_id=owner.id
    )
    project_a = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="AAA",
        name="A",
        description=None,
        owner_id=owner.id,
    )
    project_b = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="BBB",
        name="B",
        description=None,
        owner_id=owner.id,
    )
    task_a = await _make_task(db_session, project_a, owner.id)
    task_b = await _make_task(db_session, project_b, owner.id)
    await task_assignee_repository.assign_many(
        db_session, task_id=task_a.id, user_ids=[owner.id]
    )
    await task_assignee_repository.assign_many(
        db_session, task_id=task_b.id, user_ids=[owner.id]
    )

    await task_assignee_repository.remove_for_project(
        db_session, project_id=project_a.id, user_id=owner.id
    )

    a = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project_a.id, task_id=task_a.id
    )
    b = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project_b.id, task_id=task_b.id
    )
    assert a.assignees == []
    assert len(b.assignees) == 1


async def test_remove_for_org_affects_every_project_in_the_org(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "tarepo-owner6@example.com")
    org = await organization_repository.create_organization(
        db_session, name="Org", owner_id=owner.id
    )
    other_org = await organization_repository.create_organization(
        db_session, name="Other Org", owner_id=owner.id
    )
    project_a = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="AAA",
        name="A",
        description=None,
        owner_id=owner.id,
    )
    project_c = await project_repository.create_project(
        db_session,
        org_id=other_org.id,
        key="CCC",
        name="C",
        description=None,
        owner_id=owner.id,
    )
    task_a = await _make_task(db_session, project_a, owner.id)
    task_c = await _make_task(db_session, project_c, owner.id)
    await task_assignee_repository.assign_many(
        db_session, task_id=task_a.id, user_ids=[owner.id]
    )
    await task_assignee_repository.assign_many(
        db_session, task_id=task_c.id, user_ids=[owner.id]
    )

    await task_assignee_repository.remove_for_org(
        db_session, org_id=org.id, user_id=owner.id
    )

    a = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project_a.id, task_id=task_a.id
    )
    c = await task_repository.get_scoped_with_assignees(
        db_session, project_id=project_c.id, task_id=task_c.id
    )
    assert a.assignees == []
    assert len(c.assignees) == 1
