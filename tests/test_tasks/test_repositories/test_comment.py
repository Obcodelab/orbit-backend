from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_repository
from modules.tasks.repositories import comment_repository, task_repository
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


async def _make_task(db_session: AsyncSession, owner_id) -> object:
    org = await organization_repository.create_organization(
        db_session, name="Test Org", owner_id=owner_id
    )
    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner_id,
    )
    return await task_repository.create_task(
        db_session,
        org_id=org.id,
        project_id=project.id,
        number=1,
        parent_task_id=None,
        title="Fix bug",
        description=None,
        priority=TaskPriority.MEDIUM,
        labels=None,
        due_date=None,
        created_by=owner_id,
    )


async def test_create_comment_sets_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "crepo-owner1@example.com")
    task = await _make_task(db_session, owner.id)

    comment = await comment_repository.create_comment(
        db_session, task_id=task.id, user_id=owner.id, body="hello"
    )

    assert comment.task_id == task.id
    assert comment.body == "hello"


async def test_get_by_id_with_user_eager_loads_user(db_session: AsyncSession):
    owner = await _make_user(db_session, "crepo-owner2@example.com")
    task = await _make_task(db_session, owner.id)
    comment = await comment_repository.create_comment(
        db_session, task_id=task.id, user_id=owner.id, body="hello"
    )

    result = await comment_repository.get_by_id_with_user(
        db_session, comment_id=comment.id
    )

    assert result is not None
    assert result.user.email == "crepo-owner2@example.com"


async def test_get_scoped_returns_none_for_wrong_task(db_session: AsyncSession):
    owner = await _make_user(db_session, "crepo-owner4@example.com")
    task_a = await _make_task(db_session, owner.id)
    task_b = await _make_task(db_session, owner.id)
    comment = await comment_repository.create_comment(
        db_session, task_id=task_a.id, user_id=owner.id, body="hello"
    )

    result = await comment_repository.get_scoped(
        db_session, task_id=task_b.id, comment_id=comment.id
    )

    assert result is None


async def test_update_body_persists_changes(db_session: AsyncSession):
    owner = await _make_user(db_session, "crepo-owner5@example.com")
    task = await _make_task(db_session, owner.id)
    comment = await comment_repository.create_comment(
        db_session, task_id=task.id, user_id=owner.id, body="hello"
    )

    updated = await comment_repository.update_body(
        db_session, comment=comment, body="edited"
    )

    assert updated.body == "edited"


async def test_get_for_task_orders_chronologically(db_session: AsyncSession):
    owner = await _make_user(db_session, "crepo-owner3@example.com")
    task = await _make_task(db_session, owner.id)
    await comment_repository.create_comment(
        db_session, task_id=task.id, user_id=owner.id, body="first"
    )
    await comment_repository.create_comment(
        db_session, task_id=task.id, user_id=owner.id, body="second"
    )

    comments, total = await comment_repository.get_for_task(
        db_session, task_id=task.id, limit=20, offset=0
    )

    assert total == 2
    assert [c.body for c in comments] == ["first", "second"]
