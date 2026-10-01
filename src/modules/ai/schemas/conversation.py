from datetime import datetime

from pydantic import UUID7, BaseModel, Field

from core.schemas import FROM_ORM


class AIConversationResponse(BaseModel):
    model_config = FROM_ORM

    conversation_id: UUID7 = Field(validation_alias="id")
    title: str | None
    created_at: datetime
