from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.types import RealtimeEventType
from core.websocket_manager import build_event, connection_manager
from modules.ai.chat import generate_answer, generate_answer_stream
from modules.ai.exceptions import AssistantUnavailableError, ConversationNotFoundError
from modules.ai.models import DocumentChunk
from modules.ai.repositories import (
    AIConversationRepository,
    AIMessageRepository,
    AskIdempotencyKeyRepository,
    ai_conversation_repository,
    ai_message_repository,
    ask_idempotency_key_repository,
)
from modules.ai.retrieval import retrieve_relevant_chunks
from modules.ai.schemas import AIMessageResponse, Citation
from modules.ai.types import AIMessageRole
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.models import Project
from modules.projects.types import ProjectStatus

_NO_CONTEXT_ANSWER = (
    "I couldn't find anything relevant in this project's documents to answer that."
)
_SNIPPET_LENGTH = 200
_TITLE_LENGTH = 60
_TOP_K = 5


def _derive_title(question: str) -> str:
    question = question.strip()
    if len(question) <= _TITLE_LENGTH:
        return question
    return question[:_TITLE_LENGTH].rstrip() + "…"


def _build_context(chunks: list[DocumentChunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))


def _build_citations(chunks: list[DocumentChunk]) -> list[Citation]:
    return [
        Citation(
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            snippet=chunk.content[:_SNIPPET_LENGTH],
        )
        for chunk in chunks
    ]


class AssistantService:
    def __init__(
        self,
        conversation_repo: AIConversationRepository,
        message_repo: AIMessageRepository,
        idempotency_repo: AskIdempotencyKeyRepository,
    ) -> None:
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.idempotency_repo = idempotency_repo

    async def ask(
        self,
        session: AsyncSession,
        *,
        project: Project,
        conversation_id: UUID,
        user_id: UUID,
        question: str,
        stream: bool,
        idempotency_key: str | None = None,
    ) -> AIMessageResponse:
        """idempotency_key is recorded only after the answer is saved, not
        claimed up front — a true simultaneous double-fire could still
        slip through, but the realistic trigger (a reload seconds later)
        is fully covered, which is the actual risk this exists for."""
        if project.status == ProjectStatus.ARCHIVED:
            raise ProjectArchivedError

        conversation = await self.conversation_repo.get_scoped(
            session, project_id=project.id, conversation_id=conversation_id
        )
        if not conversation:
            raise ConversationNotFoundError

        if idempotency_key is not None:
            existing_id = await self.idempotency_repo.get_message_id(
                session, user_id=user_id, key=idempotency_key
            )
            if existing_id is not None:
                existing = await self.message_repo.get_by_id(session, existing_id)
                if existing is not None:
                    return AIMessageResponse.model_validate(existing)

        await self.message_repo.create_message(
            session,
            conversation_id=conversation.id,
            role=AIMessageRole.USER,
            content=question,
        )
        if conversation.title is None:
            await self.conversation_repo.set_title(
                session, conversation=conversation, title=_derive_title(question)
            )

        try:
            chunks = await retrieve_relevant_chunks(
                session, project_id=project.id, query=question, top_k=_TOP_K
            )
            if not chunks:
                answer_text, citations = _NO_CONTEXT_ANSWER, []
            elif stream:
                context = _build_context(chunks)
                answer_text = await self._stream_answer(
                    project_id=project.id,
                    user_id=user_id,
                    conversation_id=conversation.id,
                    question=question,
                    context=context,
                )
                citations = _build_citations(chunks)
            else:
                context = _build_context(chunks)
                answer_text = await generate_answer(question=question, context=context)
                citations = _build_citations(chunks)
        except Exception as exc:
            raise AssistantUnavailableError from exc

        answer_message = await self.message_repo.create_message(
            session,
            conversation_id=conversation.id,
            role=AIMessageRole.ASSISTANT,
            content=answer_text,
            citations=[c.model_dump(mode="json") for c in citations],
        )
        if idempotency_key is not None:
            await self.idempotency_repo.record(
                session,
                user_id=user_id,
                key=idempotency_key,
                message_id=answer_message.id,
            )
        response = AIMessageResponse.model_validate(answer_message)
        await connection_manager.send_to_user(
            user_id,
            build_event(
                event_type=RealtimeEventType.AI_ANSWER_COMPLETE,
                project_id=project.id,
                data=response.model_dump(mode="json"),
                actor_id=user_id,
            ),
        )
        return response

    async def _stream_answer(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        conversation_id: UUID,
        question: str,
        context: str,
    ) -> str:
        pieces: list[str] = []
        async for delta in generate_answer_stream(question=question, context=context):
            pieces.append(delta)
            await connection_manager.send_to_user(
                user_id,
                build_event(
                    event_type=RealtimeEventType.AI_ANSWER_CHUNK,
                    project_id=project_id,
                    data={"conversation_id": str(conversation_id), "delta": delta},
                    actor_id=user_id,
                ),
            )
        return "".join(pieces)


assistant_service = AssistantService(
    conversation_repo=ai_conversation_repository,
    message_repo=ai_message_repository,
    idempotency_repo=ask_idempotency_key_repository,
)
