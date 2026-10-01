import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.ai.exceptions import ConversationNotFoundError
from modules.ai.services import conversation_service
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.repositories import project_repository
from modules.projects.types import ProjectStatus


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


async def test_create_conversation_succeeds(db_session: AsyncSession):
    owner = await _make_user(db_session, "conv-svc-owner1@example.com")
    project = await _make_project(db_session, owner.id)

    conversation = await conversation_service.create_conversation(
        db_session, project=project, user_id=owner.id
    )

    assert conversation.title is None


async def test_create_conversation_raises_when_project_archived(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "conv-svc-owner2@example.com")
    project = await _make_project(db_session, owner.id)
    project = await project_repository.update_fields(
        db_session, project=project, updates={"status": ProjectStatus.ARCHIVED}
    )

    with pytest.raises(ProjectArchivedError):
        await conversation_service.create_conversation(
            db_session, project=project, user_id=owner.id
        )


async def test_list_messages_raises_when_conversation_not_found(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "conv-svc-owner3@example.com")
    project = await _make_project(db_session, owner.id)

    with pytest.raises(ConversationNotFoundError):
        await conversation_service.list_messages(
            db_session,
            project_id=project.id,
            conversation_id=owner.id,
            order=None,
            limit=20,
            offset=0,
        )


async def test_list_messages_works_for_archived_project(db_session: AsyncSession):
    """History stays readable in an archived project — only starting a
    new conversation or asking a question is blocked."""
    owner = await _make_user(db_session, "conv-svc-owner4@example.com")
    project = await _make_project(db_session, owner.id)
    conversation = await conversation_service.create_conversation(
        db_session, project=project, user_id=owner.id
    )
    await project_repository.update_fields(
        db_session, project=project, updates={"status": ProjectStatus.ARCHIVED}
    )

    page = await conversation_service.list_messages(
        db_session,
        project_id=project.id,
        conversation_id=conversation.conversation_id,
        order=None,
        limit=20,
        offset=0,
    )

    assert page.total == 0
