from datetime import datetime

from pydantic import UUID7, BaseModel, Field

from core.schemas import FROM_ORM
from modules.ai.types import AIMessageRole


class Citation(BaseModel):
    document_id: UUID7
    chunk_id: UUID7
    snippet: str


class AIMessageResponse(BaseModel):
    model_config = FROM_ORM

    message_id: UUID7 = Field(validation_alias="id")
    role: AIMessageRole
    content: str
    citations: list[Citation] | None
    created_at: datetime


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    stream: bool = False
    idempotency_key: str | None = Field(default=None, max_length=255)
