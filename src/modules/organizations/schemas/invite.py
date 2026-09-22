from pydantic import UUID7, BaseModel, ConfigDict, EmailStr, Field

from core.schemas import FROM_ORM
from modules.organizations.types import OrganizationRole


class OrgSummary(BaseModel):
    model_config = FROM_ORM

    org_id: UUID7 = Field(validation_alias="id")
    name: str


class InviterSummary(BaseModel):
    model_config = FROM_ORM

    user_id: UUID7 = Field(validation_alias="id")
    first_name: str
    last_name: str


class MyInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invite_id: UUID7 = Field(validation_alias="id")
    organization: OrgSummary
    role: OrganizationRole
    inviter: InviterSummary | None


class OrgInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invite_id: UUID7 = Field(validation_alias="id")
    email: EmailStr
    role: OrganizationRole
    inviter: InviterSummary | None
