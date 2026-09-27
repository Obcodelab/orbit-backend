import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.services import organization_service
from modules.projects.services import project_service
from modules.tasks.exceptions import (
    CommentNotFoundError,
    NotCommentAuthorError,
    TaskNotFoundError,
)
from modules.tasks.services import comment_service, task_service
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


async def _make_project_and_task(db_session: AsyncSession, owner: User):
    org = await organization_service.create_organization(
        db_session, name="Test Org", owner=owner
    )
    project = await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )
    task = await task_service.create_task(
        db_session,
        project=project,
        title="Fix bug",
        description=None,
        assignee_ids=[],
        parent_task_id=None,
        priority=TaskPriority.MEDIUM,
        labels=None,
        due_date=None,
        creator_id=owner.id,
    )
    return project, task


async def test_add_comment_raises_when_task_not_found(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner1@example.com")
    project, _ = await _make_project_and_task(db_session, owner)

    with pytest.raises(TaskNotFoundError):
        await comment_service.add_comment(
            db_session,
            project_id=project.id,
            task_id=owner.id,
            user_id=owner.id,
            body="hello",
        )


async def test_add_comment_succeeds(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner2@example.com")
    project, task = await _make_project_and_task(db_session, owner)

    comment = await comment_service.add_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        user_id=owner.id,
        body="hello",
    )

    assert comment.body == "hello"
    assert comment.user.email == owner.email


async def test_list_for_task_returns_paginated_comments(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner3@example.com")
    project, task = await _make_project_and_task(db_session, owner)
    await comment_service.add_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        user_id=owner.id,
        body="first",
    )

    page = await comment_service.list_for_task(
        db_session, project_id=project.id, task_id=task.task_id, limit=20, offset=0
    )

    assert page.total == 1
    assert page.items[0].body == "first"


async def test_update_comment_succeeds_for_author(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner4@example.com")
    project, task = await _make_project_and_task(db_session, owner)
    comment = await comment_service.add_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        user_id=owner.id,
        body="first",
    )

    updated = await comment_service.update_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        comment_id=comment.comment_id,
        user_id=owner.id,
        body="edited",
    )

    assert updated.body == "edited"


async def test_update_comment_raises_when_not_author(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner5@example.com")
    stranger = await _make_user(db_session, "csvc-stranger5@example.com")
    project, task = await _make_project_and_task(db_session, owner)
    comment = await comment_service.add_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        user_id=owner.id,
        body="first",
    )

    with pytest.raises(NotCommentAuthorError):
        await comment_service.update_comment(
            db_session,
            project_id=project.id,
            task_id=task.task_id,
            comment_id=comment.comment_id,
            user_id=stranger.id,
            body="edited",
        )


async def test_update_comment_raises_when_not_found(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner6@example.com")
    project, task = await _make_project_and_task(db_session, owner)

    with pytest.raises(CommentNotFoundError):
        await comment_service.update_comment(
            db_session,
            project_id=project.id,
            task_id=task.task_id,
            comment_id=owner.id,
            user_id=owner.id,
            body="edited",
        )


async def test_delete_comment_succeeds_for_author(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner7@example.com")
    project, task = await _make_project_and_task(db_session, owner)
    comment = await comment_service.add_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        user_id=owner.id,
        body="first",
    )

    await comment_service.delete_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        comment_id=comment.comment_id,
        user_id=owner.id,
    )

    page = await comment_service.list_for_task(
        db_session, project_id=project.id, task_id=task.task_id, limit=20, offset=0
    )
    assert page.total == 0


async def test_delete_comment_raises_when_not_author(db_session: AsyncSession):
    owner = await _make_user(db_session, "csvc-owner8@example.com")
    stranger = await _make_user(db_session, "csvc-stranger8@example.com")
    project, task = await _make_project_and_task(db_session, owner)
    comment = await comment_service.add_comment(
        db_session,
        project_id=project.id,
        task_id=task.task_id,
        user_id=owner.id,
        body="first",
    )

    with pytest.raises(NotCommentAuthorError):
        await comment_service.delete_comment(
            db_session,
            project_id=project.id,
            task_id=task.task_id,
            comment_id=comment.comment_id,
            user_id=stranger.id,
        )
