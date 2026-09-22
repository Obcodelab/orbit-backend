import re

from pydantic import UUID7, BaseModel, ConfigDict, Field, field_validator

from core.schemas import FROM_ORM
from modules.organizations.schemas import MemberUserSummary
from modules.projects.types import ProjectRole, ProjectStatus

_KEY_RE = re.compile(r"^[A-Z0-9]{2,10}$")


def _reject_owner(role: ProjectRole) -> ProjectRole:
    """Ownership isn't grantable through membership endpoints — there's no
    transfer flow, so `owner` is set once at project creation and never
    again."""
    if role == ProjectRole.OWNER:
        raise ValueError("Cannot assign the owner role — ownership isn't transferable")
    return role


class ProjectCreateRequest(BaseModel):
    key: str = Field(..., min_length=2, max_length=10)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError("Key must be 2-10 uppercase letters/digits (e.g. ORB)")
        return v


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None


class ProjectResponse(BaseModel):
    model_config = FROM_ORM

    project_id: UUID7 = Field(validation_alias="id")
    org_id: UUID7
    key: str
    name: str
    description: str | None
    status: ProjectStatus
    owner_id: UUID7


class MyProjectResponse(ProjectResponse):
    role: ProjectRole


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: ProjectRole
    user: MemberUserSummary


class AddProjectMemberRequest(BaseModel):
    user_id: UUID7
    role: ProjectRole = ProjectRole.MEMBER

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: ProjectRole) -> ProjectRole:
        return _reject_owner(v)


class UpdateProjectMemberRoleRequest(BaseModel):
    role: ProjectRole

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: ProjectRole) -> ProjectRole:
        return _reject_owner(v)
