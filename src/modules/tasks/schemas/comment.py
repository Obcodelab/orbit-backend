from datetime import datetime

from pydantic import UUID7, BaseModel, Field

from core.schemas import FROM_ORM
from modules.organizations.schemas import MemberUserSummary


class CommentCreateRequest(BaseModel):
    body: str = Field(..., min_length=1)


class CommentUpdateRequest(BaseModel):
    body: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    model_config = FROM_ORM

    comment_id: UUID7 = Field(validation_alias="id")
    user: MemberUserSummary
    body: str
    created_at: datetime
