from pydantic import UUID7, BaseModel, ConfigDict, EmailStr, Field, field_validator

from modules.organizations.types import OrganizationRole

# populate_by_name lets response objects also be built with the real field
# name (e.g. org_id=...) rather than only the ORM-matching alias (id=...).
_FROM_ORM = ConfigDict(from_attributes=True, populate_by_name=True)


def _reject_owner(role: OrganizationRole) -> OrganizationRole:
    """Ownership isn't grantable through membership endpoints — there's no
    transfer flow, so `owner` is set once at org creation and never again."""
    if role == OrganizationRole.OWNER:
        raise ValueError("Cannot assign the owner role — ownership isn't transferable")
    return role


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrganizationUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    model_config = _FROM_ORM

    org_id: UUID7 = Field(validation_alias="id")
    name: str
    owner_id: UUID7


class MyOrganizationResponse(OrganizationResponse):
    role: OrganizationRole


class MemberUserSummary(BaseModel):
    model_config = _FROM_ORM

    user_id: UUID7 = Field(validation_alias="id")
    email: EmailStr
    first_name: str
    last_name: str


class OrganizationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: UUID7 = Field(validation_alias="id")
    org_id: UUID7
    role: OrganizationRole
    user: MemberUserSummary


class AddOrganizationMemberRequest(BaseModel):
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: OrganizationRole) -> OrganizationRole:
        return _reject_owner(v)


class UpdateMemberRoleRequest(BaseModel):
    role: OrganizationRole

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: OrganizationRole) -> OrganizationRole:
        return _reject_owner(v)
