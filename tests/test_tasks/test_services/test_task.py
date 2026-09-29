import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_member_repository
from modules.organizations.services import organization_service
from modules.organizations.types import OrganizationRole
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.repositories import project_member_repository, project_repository
from modules.projects.services import project_service
from modules.projects.types import ProjectRole, ProjectStatus
from modules.tasks.exceptions import (
    AssigneeNotProjectMemberError,
    ParentTaskNotFoundError,
    StatusChangeForbiddenError,
    TaskNotFoundError,
)
from modules.tasks.services import task_service
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


async def _make_project(db_session: AsyncSession, owner: User) -> object:
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


async def _create_task(db_session, project, owner_id, **overrides):
    defaults = dict(
        title="Fix bug",
        description=None,
        assignee_ids=[],
        parent_task_id=None,
        priority=TaskPriority.MEDIUM,
        labels=None,
        due_date=None,
        creator_id=owner_id,
    )
    defaults.update(overrides)
    return await task_service.create_task(db_session, project=project, **defaults)


async def test_create_task_generates_sequential_numbers(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner1@example.com")
    project = await _make_project(db_session, owner)

    first = await _create_task(db_session, project, owner.id, title="First")
    second = await _create_task(db_session, project, owner.id, title="Second")

    assert first.key == "ORB-1"
    assert second.key == "ORB-2"


async def test_create_task_raises_when_project_archived(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner2@example.com")
    project = await _make_project(db_session, owner)
    project = await project_repository.update_fields(
        db_session, project=project, updates={"status": ProjectStatus.ARCHIVED}
    )

    with pytest.raises(ProjectArchivedError):
        await _create_task(db_session, project, owner.id)


async def test_create_task_raises_when_assignee_not_project_member(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "tsvc-owner3@example.com")
    stranger = await _make_user(db_session, "tsvc-stranger3@example.com")
    project = await _make_project(db_session, owner)

    with pytest.raises(AssigneeNotProjectMemberError):
        await _create_task(db_session, project, owner.id, assignee_ids=[stranger.id])


async def test_create_task_with_valid_assignees_succeeds(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner4@example.com")
    project = await _make_project(db_session, owner)

    task = await _create_task(db_session, project, owner.id, assignee_ids=[owner.id])

    assert len(task.assignees) == 1
    assert task.assignees[0].email == owner.email


async def test_create_task_raises_when_parent_not_found(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner4b@example.com")
    project = await _make_project(db_session, owner)

    with pytest.raises(ParentTaskNotFoundError):
        await _create_task(db_session, project, owner.id, parent_task_id=owner.id)


async def test_create_task_with_valid_parent_succeeds(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner4c@example.com")
    project = await _make_project(db_session, owner)
    parent = await _create_task(db_session, project, owner.id, title="Parent")

    child = await _create_task(
        db_session, project, owner.id, title="Child", parent_task_id=parent.task_id
    )

    assert child.parent_task_id == parent.task_id


async def test_list_for_project_filters_by_status(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner5@example.com")
    project = await _make_project(db_session, owner)
    await _create_task(db_session, project, owner.id, title="Todo")

    page = await task_service.list_for_project(
        db_session,
        project_id=project.id,
        status_filter=TaskStatus.DONE,
        priority_filter=None,
        assignee_id=None,
        label=None,
        parent_id=None,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert page.total == 0


async def test_get_task_raises_when_not_found(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner6@example.com")
    other_owner = await _make_user(db_session, "tsvc-owner6b@example.com")
    project = await _make_project(db_session, owner)
    other_project = await _make_project(db_session, other_owner)
    task = await _create_task(db_session, project, owner.id)

    with pytest.raises(TaskNotFoundError):
        await task_service.get_task(
            db_session, project_id=other_project.id, task_id=task.task_id
        )


async def test_update_task_replaces_assignees(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner7@example.com")
    member = await _make_user(db_session, "tsvc-member7@example.com")
    project = await _make_project(db_session, owner)
    await organization_member_repository.add_member(
        db_session,
        org_id=project.org_id,
        user_id=member.id,
        role=OrganizationRole.MEMBER,
    )
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )
    task = await _create_task(db_session, project, owner.id, assignee_ids=[owner.id])

    updated, newly_added = await task_service.update_task(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        updates={},
        assignee_ids=[member.id],
    )

    assert {a.email for a in updated.assignees} == {member.email}
    assert newly_added == [member.id]


async def test_update_task_returns_no_newly_added_when_assignees_unchanged(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "tsvc-owner7b@example.com")
    project = await _make_project(db_session, owner)
    task = await _create_task(db_session, project, owner.id, assignee_ids=[owner.id])

    _, newly_added = await task_service.update_task(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        updates={},
        assignee_ids=[owner.id],
    )

    assert newly_added == []


async def test_update_task_returns_no_newly_added_when_assignee_ids_not_given(
    db_session: AsyncSession,
):
    """Editing an unrelated field shouldn't look like a reassignment —
    this is exactly what would spuriously re-notify existing assignees
    if update_task returned everyone in assignee_ids instead of a diff."""
    owner = await _make_user(db_session, "tsvc-owner7c@example.com")
    project = await _make_project(db_session, owner)
    task = await _create_task(db_session, project, owner.id, assignee_ids=[owner.id])

    _, newly_added = await task_service.update_task(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        updates={"title": "Renamed"},
        assignee_ids=None,
    )

    assert newly_added == []


async def test_update_task_raises_when_assignee_not_project_member(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "tsvc-owner8@example.com")
    stranger = await _make_user(db_session, "tsvc-stranger8@example.com")
    project = await _make_project(db_session, owner)
    task = await _create_task(db_session, project, owner.id)

    with pytest.raises(AssigneeNotProjectMemberError):
        await task_service.update_task(
            db_session,
            project_id=project.id,
            task_id=task.task_id,
            updates={},
            assignee_ids=[stranger.id],
        )


async def test_update_status_allowed_for_assignee(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner9@example.com")
    member = await _make_user(db_session, "tsvc-member9@example.com")
    project = await _make_project(db_session, owner)
    await organization_member_repository.add_member(
        db_session,
        org_id=project.org_id,
        user_id=member.id,
        role=OrganizationRole.MEMBER,
    )
    member_row = await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )
    task = await _create_task(db_session, project, owner.id, assignee_ids=[member.id])

    updated = await task_service.update_status(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        status=TaskStatus.IN_PROGRESS,
        caller=member_row,
    )

    assert updated.status == TaskStatus.IN_PROGRESS


async def test_update_status_forbidden_for_non_assignee_member(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "tsvc-owner10@example.com")
    member = await _make_user(db_session, "tsvc-member10@example.com")
    project = await _make_project(db_session, owner)
    await organization_member_repository.add_member(
        db_session,
        org_id=project.org_id,
        user_id=member.id,
        role=OrganizationRole.MEMBER,
    )
    member_row = await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )
    task = await _create_task(db_session, project, owner.id)

    with pytest.raises(StatusChangeForbiddenError):
        await task_service.update_status(
            db_session,
            project_id=project.id,
            task_id=task.task_id,
            status=TaskStatus.IN_PROGRESS,
            caller=member_row,
        )


async def test_update_status_to_done_stamps_resolved_at(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner12@example.com")
    project = await _make_project(db_session, owner)
    task = await _create_task(db_session, project, owner.id, assignee_ids=[owner.id])
    member_row = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=owner.id
    )

    updated = await task_service.update_status(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        status=TaskStatus.DONE,
        caller=member_row,
    )

    assert updated.resolved_at is not None


async def test_reopening_a_done_task_clears_resolved_at(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner13@example.com")
    project = await _make_project(db_session, owner)
    task = await _create_task(db_session, project, owner.id, assignee_ids=[owner.id])
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

    reopened = await task_service.update_status(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        status=TaskStatus.TODO,
        caller=member_row,
    )

    assert reopened.resolved_at is None


async def test_delete_task_raises_when_not_found(db_session: AsyncSession):
    owner = await _make_user(db_session, "tsvc-owner11@example.com")
    project = await _make_project(db_session, owner)

    with pytest.raises(TaskNotFoundError):
        await task_service.delete_task(
            db_session, project_id=project.id, task_id=owner.id
        )
