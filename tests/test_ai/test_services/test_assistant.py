import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

import modules.ai.services.assistant as assistant_module
from core.security import hash_password
from core.websocket_manager import connection_manager
from modules.ai.exceptions import AssistantUnavailableError, ConversationNotFoundError
from modules.ai.repositories import (
    ai_conversation_repository,
    ai_message_repository,
    document_chunk_repository,
)
from modules.ai.services import assistant_service
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.files.repositories import document_repository
from modules.organizations.repositories import organization_repository
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.repositories import project_repository
from modules.projects.types import ProjectStatus
from tests.test_core.test_websocket_manager import FakeWebSocket


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Service",
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


async def _add_chunk(db_session: AsyncSession, *, project, uploader_id):
    document_id = uuid7()
    await document_repository.create_document(
        db_session,
        id=document_id,
        org_id=project.org_id,
        project_id=project.id,
        task_id=None,
        uploader_id=uploader_id,
        filename="spec.txt",
        file_size=100,
        mime_type="text/plain",
        storage_path=f"{project.id}/{document_id}/spec.txt",
        content_hash=str(document_id),
    )
    await document_chunk_repository.create_chunks(
        db_session,
        document_id=document_id,
        chunks=["relevant content"],
        embeddings=[[0.1] * 768],
    )


async def test_ask_raises_when_project_archived(db_session: AsyncSession):
    owner = await _make_user(db_session, "assistant-owner1@example.com")
    project = await _make_project(db_session, owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )
    project = await project_repository.update_fields(
        db_session, project=project, updates={"status": ProjectStatus.ARCHIVED}
    )

    with pytest.raises(ProjectArchivedError):
        await assistant_service.ask(
            db_session,
            project=project,
            conversation_id=conversation.id,
            user_id=owner.id,
            question="anything",
            stream=False,
        )


async def test_ask_raises_when_conversation_not_found(db_session: AsyncSession):
    owner = await _make_user(db_session, "assistant-owner2@example.com")
    project = await _make_project(db_session, owner.id)

    with pytest.raises(ConversationNotFoundError):
        await assistant_service.ask(
            db_session,
            project=project,
            conversation_id=owner.id,
            user_id=owner.id,
            question="anything",
            stream=False,
        )


async def test_ask_returns_fixed_response_when_no_chunks(db_session: AsyncSession):
    owner = await _make_user(db_session, "assistant-owner3@example.com")
    project = await _make_project(db_session, owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )

    response = await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="anything",
        stream=False,
    )

    assert "couldn't find anything relevant" in response.content
    assert response.citations == []


async def test_ask_answers_with_citations_when_chunks_exist(db_session: AsyncSession):
    owner = await _make_user(db_session, "assistant-owner4@example.com")
    project = await _make_project(db_session, owner.id)
    await _add_chunk(db_session, project=project, uploader_id=owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )

    response = await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="what's in the spec?",
        stream=False,
    )

    assert response.content == "fake answer for: what's in the spec?"
    assert len(response.citations) == 1
    assert response.citations[0].snippet == "relevant content"


async def test_ask_derives_title_only_on_first_message(db_session: AsyncSession):
    owner = await _make_user(db_session, "assistant-owner5@example.com")
    project = await _make_project(db_session, owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )

    await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="first question",
        stream=False,
    )
    refreshed = await ai_conversation_repository.get_scoped(
        db_session, project_id=project.id, conversation_id=conversation.id
    )
    assert refreshed.title == "first question"

    await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="second question",
        stream=False,
    )
    refreshed_again = await ai_conversation_repository.get_scoped(
        db_session, project_id=project.id, conversation_id=conversation.id
    )
    assert refreshed_again.title == "first question"


async def test_ask_stream_sends_chunk_events_and_joins_answer(db_session: AsyncSession):
    owner = await _make_user(db_session, "assistant-owner6@example.com")
    project = await _make_project(db_session, owner.id)
    await _add_chunk(db_session, project=project, uploader_id=owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )
    ws = FakeWebSocket()
    await connection_manager.connect(owner.id, [project.id], ws)
    ws.received.clear()

    try:
        response = await assistant_service.ask(
            db_session,
            project=project,
            conversation_id=conversation.id,
            user_id=owner.id,
            question="stream this",
            stream=True,
        )
    finally:
        await connection_manager.disconnect(ws)

    assert response.content == "fake streamed answer"
    chunk_events = [m for m in ws.received if m["type"] == "ai.answer_chunk"]
    complete_events = [m for m in ws.received if m["type"] == "ai.answer_complete"]
    assert [e["data"]["delta"] for e in chunk_events] == [
        "fake ",
        "streamed ",
        "answer",
    ]
    assert len(complete_events) == 1
    assert complete_events[0]["data"]["content"] == "fake streamed answer"


async def test_ask_with_same_idempotency_key_does_not_duplicate(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "assistant-owner7@example.com")
    project = await _make_project(db_session, owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )
    key = str(uuid7())

    first = await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="what's in the spec?",
        stream=False,
        idempotency_key=key,
    )
    second = await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="what's in the spec?",
        stream=False,
        idempotency_key=key,
    )

    assert first.message_id == second.message_id
    _, total = await ai_message_repository.get_for_conversation(
        db_session, conversation_id=conversation.id, order=None, limit=20, offset=0
    )
    assert total == 2  # one user message + one assistant message, not four


async def test_ask_with_different_idempotency_keys_creates_separate_answers(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "assistant-owner8@example.com")
    project = await _make_project(db_session, owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )

    first = await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="first",
        stream=False,
        idempotency_key=str(uuid7()),
    )
    second = await assistant_service.ask(
        db_session,
        project=project,
        conversation_id=conversation.id,
        user_id=owner.id,
        question="second",
        stream=False,
        idempotency_key=str(uuid7()),
    )

    assert first.message_id != second.message_id


async def test_ask_raises_assistant_unavailable_when_generation_fails(
    db_session: AsyncSession, monkeypatch
):
    async def _broken_generate_answer(*, question, context):
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr(assistant_module, "generate_answer", _broken_generate_answer)
    owner = await _make_user(db_session, "assistant-owner9@example.com")
    project = await _make_project(db_session, owner.id)
    await _add_chunk(db_session, project=project, uploader_id=owner.id)
    conversation = await ai_conversation_repository.create_conversation(
        db_session, org_id=project.org_id, project_id=project.id, user_id=owner.id
    )

    with pytest.raises(AssistantUnavailableError):
        await assistant_service.ask(
            db_session,
            project=project,
            conversation_id=conversation.id,
            user_id=owner.id,
            question="what's in the spec?",
            stream=False,
        )
