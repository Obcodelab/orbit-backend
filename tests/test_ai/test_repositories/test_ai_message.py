from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.ai.repositories import ai_conversation_repository, ai_message_repository
from modules.ai.types import AIMessageRole
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


async def _make_conversation(db_session: AsyncSession, email: str):
    owner = await _make_user(db_session, email)
    org = await organization_repository.create_organization(
        db_session, name="Test Org", owner_id=owner.id
    )
    project = await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner.id,
    )
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=org.id, project_id=project.id, user_id=owner.id
    )
    return conversation


async def test_create_message_sets_fields(db_session: AsyncSession):
    conversation = await _make_conversation(db_session, "msg-repo-owner1@example.com")

    message = await ai_message_repository.create_message(
        db_session,
        conversation_id=conversation.id,
        role=AIMessageRole.USER,
        content="What's our rate limiting strategy?",
    )

    assert message.role == AIMessageRole.USER
    assert message.citations is None


async def test_create_message_stores_citations(db_session: AsyncSession):
    conversation = await _make_conversation(db_session, "msg-repo-owner2@example.com")
    citations = [{"document_id": "x", "chunk_id": "y", "snippet": "..."}]

    message = await ai_message_repository.create_message(
        db_session,
        conversation_id=conversation.id,
        role=AIMessageRole.ASSISTANT,
        content="Here's the answer.",
        citations=citations,
    )

    assert message.citations == citations


async def test_get_for_conversation_defaults_to_ascending(db_session: AsyncSession):
    conversation = await _make_conversation(db_session, "msg-repo-owner3@example.com")
    await ai_message_repository.create_message(
        db_session,
        conversation_id=conversation.id,
        role=AIMessageRole.USER,
        content="first",
    )
    await ai_message_repository.create_message(
        db_session,
        conversation_id=conversation.id,
        role=AIMessageRole.ASSISTANT,
        content="second",
    )

    messages, total = await ai_message_repository.get_for_conversation(
        db_session, conversation_id=conversation.id, order=None, limit=20, offset=0
    )

    assert total == 2
    assert [m.content for m in messages] == ["first", "second"]
