from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from core.security import hash_password
from modules.ai.repositories import (
    ai_conversation_repository,
    ai_message_repository,
    ask_idempotency_key_repository,
)
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


async def _make_message(db_session: AsyncSession, owner: User):
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
    return await ai_message_repository.create_message(
        db_session,
        conversation_id=conversation.id,
        role=AIMessageRole.ASSISTANT,
        content="an answer",
    )


async def test_get_message_id_returns_none_when_not_recorded(db_session: AsyncSession):
    owner = await _make_user(db_session, "idem-repo-owner1@example.com")

    result = await ask_idempotency_key_repository.get_message_id(
        db_session, user_id=owner.id, key=str(uuid7())
    )

    assert result is None


async def test_record_then_get_message_id_roundtrips(db_session: AsyncSession):
    owner = await _make_user(db_session, "idem-repo-owner2@example.com")
    message = await _make_message(db_session, owner)
    key = str(uuid7())

    await ask_idempotency_key_repository.record(
        db_session, user_id=owner.id, key=key, message_id=message.id
    )
    result = await ask_idempotency_key_repository.get_message_id(
        db_session, user_id=owner.id, key=key
    )

    assert result == message.id
