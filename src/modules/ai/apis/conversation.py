from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from core.config import settings
from core.dependencies import AuthenticatedUser, DBSession, PaginationParams
from core.pagination import Page
from core.rate_limit import limiter
from core.types import SortOrder
from modules.ai.exceptions import (
    AssistantUnavailableError,
    ConversationNotFoundError,
    NotConversationOwnerError,
)
from modules.ai.schemas import (
    AIConversationResponse,
    AIMessageResponse,
    AskRequest,
    ConversationUpdateRequest,
)
from modules.ai.services import assistant_service, conversation_service
from modules.projects.dependencies import AnyProjectMember
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.repositories import project_repository

conversation_router = APIRouter(tags=["AI Assistant"])

ai_rate_limit = limiter.limit(settings.RATE_LIMIT_AI)


@conversation_router.post(
    "/projects/{project_id}/ai/conversations", status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    project_id: UUID,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
) -> AIConversationResponse:
    project = await project_repository.get_by_id(session, project_id)
    try:
        return await conversation_service.create_conversation(
            session, project=project, user_id=user.id
        )
    except ProjectArchivedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This project is archived and is read-only"
        )


@conversation_router.get("/projects/{project_id}/ai/conversations")
async def list_conversations(
    project_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    pagination: PaginationParams,
    order: SortOrder | None = Query(default=None),
) -> Page[AIConversationResponse]:
    return await conversation_service.list_for_project(
        session,
        project_id=project_id,
        order=order,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@conversation_router.patch("/projects/{project_id}/ai/conversations/{conversation_id}")
async def update_conversation(
    project_id: UUID,
    conversation_id: UUID,
    body: ConversationUpdateRequest,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
) -> AIConversationResponse:
    try:
        return await conversation_service.update_title(
            session,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id=user.id,
            title=body.title,
        )
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    except NotConversationOwnerError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the conversation's owner can rename it"
        )


@conversation_router.delete(
    "/projects/{project_id}/ai/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    project_id: UUID,
    conversation_id: UUID,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
) -> None:
    try:
        await conversation_service.delete_conversation(
            session,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id=user.id,
        )
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    except NotConversationOwnerError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the conversation's owner can delete it"
        )


@conversation_router.get(
    "/projects/{project_id}/ai/conversations/{conversation_id}/messages"
)
async def list_messages(
    project_id: UUID,
    conversation_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    pagination: PaginationParams,
    order: SortOrder | None = Query(default=None),
) -> Page[AIMessageResponse]:
    try:
        return await conversation_service.list_messages(
            session,
            project_id=project_id,
            conversation_id=conversation_id,
            order=order,
            limit=pagination.limit,
            offset=pagination.offset,
        )
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")


@conversation_router.post(
    "/projects/{project_id}/ai/conversations/{conversation_id}/ask"
)
@ai_rate_limit
async def ask(
    request: Request,
    project_id: UUID,
    conversation_id: UUID,
    body: AskRequest,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
) -> AIMessageResponse:
    project = await project_repository.get_by_id(session, project_id)
    try:
        return await assistant_service.ask(
            session,
            project=project,
            conversation_id=conversation_id,
            user_id=user.id,
            question=body.question,
            stream=body.stream,
            idempotency_key=body.idempotency_key,
        )
    except ProjectArchivedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This project is archived and is read-only"
        )
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    except AssistantUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The AI assistant is temporarily unavailable — please try again shortly",
        )
