from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.ai.repositories import ai_conversation_repository
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_repository


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_project(db_session: AsyncSession, owner_id):
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


async def test_create_conversation_sets_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "conv-repo-owner1@example.com")
    project = await _make_project(db_session, owner.id)

    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )

    assert conversation.project_id == project.id
    assert conversation.user_id == owner.id
    assert conversation.title is None


async def test_get_scoped_returns_none_for_wrong_project(db_session: AsyncSession):
    owner = await _make_user(db_session, "conv-repo-owner2@example.com")
    project_a = await _make_project(db_session, owner.id)
    project_b = await _make_project(db_session, owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project_a.org_id, project_id=project_a.id, user_id=owner.id
    )

    result = await ai_conversation_repository.get_scoped(
        db_session, project_id=project_b.id, conversation_id=conversation.id
    )

    assert result is None


async def test_set_title_updates_and_persists(db_session: AsyncSession):
    owner = await _make_user(db_session, "conv-repo-owner3@example.com")
    project = await _make_project(db_session, owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )

    updated = await ai_conversation_repository.set_title(
        db_session, conversation=conversation, title="What's the rate limit?"
    )

    assert updated.title == "What's the rate limit?"


async def test_get_for_project_paginates_and_counts(db_session: AsyncSession):
    owner = await _make_user(db_session, "conv-repo-owner4@example.com")
    project = await _make_project(db_session, owner.id)
    for _ in range(2):
        await ai_conversation_repository.create_conversation(
            db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
        )

    conversations, total = await ai_conversation_repository.get_for_project(
        db_session, project_id=project.id, order=None, limit=20, offset=0
    )

    assert total == 2
    assert len(conversations) == 2
