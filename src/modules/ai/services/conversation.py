from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import Page
from core.types import SortOrder
from modules.ai.exceptions import ConversationNotFoundError, NotConversationOwnerError
from modules.ai.models import AIConversation
from modules.ai.repositories import (
    AIConversationRepository,
    AIMessageRepository,
    ai_conversation_repository,
    ai_message_repository,
)
from modules.ai.schemas import AIConversationResponse, AIMessageResponse
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.models import Project
from modules.projects.types import ProjectStatus


class ConversationService:
    def __init__(
        self,
        conversation_repo: AIConversationRepository,
        message_repo: AIMessageRepository,
    ) -> None:
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo

    async def create_conversation(
        self, session: AsyncSession, *, project: Project, user_id: UUID
    ) -> AIConversationResponse:
        if project.status == ProjectStatus.ARCHIVED:
            raise ProjectArchivedError
        conversation = await self.conversation_repo.create_conversation(
            session, org_id=project.org_id, project_id=project.id, user_id=user_id
        )
        return AIConversationResponse.model_validate(conversation)

    async def list_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> Page[AIConversationResponse]:
        conversations, total = await self.conversation_repo.get_for_project(
            session, project_id=project_id, order=order, limit=limit, offset=offset
        )
        items = [AIConversationResponse.model_validate(c) for c in conversations]
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def list_messages(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        conversation_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> Page[AIMessageResponse]:
        """History stays readable even in an archived project — only
        starting a conversation or asking a question is blocked."""
        conversation = await self.conversation_repo.get_scoped(
            session, project_id=project_id, conversation_id=conversation_id
        )
        if not conversation:
            raise ConversationNotFoundError
        messages, total = await self.message_repo.get_for_conversation(
            session,
            conversation_id=conversation_id,
            order=order,
            limit=limit,
            offset=offset,
        )
        items = [AIMessageResponse.model_validate(m) for m in messages]
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def _get_owned_conversation(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        conversation_id: UUID,
        user_id: UUID,
    ) -> AIConversation:
        conversation = await self.conversation_repo.get_scoped(
            session, project_id=project_id, conversation_id=conversation_id
        )
        if not conversation:
            raise ConversationNotFoundError
        if conversation.user_id != user_id:
            raise NotConversationOwnerError
        return conversation

    async def update_title(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        conversation_id: UUID,
        user_id: UUID,
        title: str,
    ) -> AIConversationResponse:
        conversation = await self._get_owned_conversation(
            session,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        conversation = await self.conversation_repo.set_title(
            session, conversation=conversation, title=title
        )
        return AIConversationResponse.model_validate(conversation)

    async def delete_conversation(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        conversation = await self._get_owned_conversation(
            session,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        await self.conversation_repo.delete_by_id(session, conversation.id)


conversation_service = ConversationService(
    conversation_repo=ai_conversation_repository, message_repo=ai_message_repository
)
