from datetime import datetime

from pydantic import UUID7, BaseModel, Field

from core.schemas import FROM_ORM
from modules.organizations.schemas import MemberUserSummary
from modules.projects.types import ActivityAction


class ActivityLogEntryResponse(BaseModel):
    model_config = FROM_ORM

    activity_id: UUID7 = Field(validation_alias="id")
    actor: MemberUserSummary
    action: ActivityAction
    target: str
    created_at: datetime
