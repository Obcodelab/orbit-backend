from datetime import datetime

from pydantic import (
    UUID7,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from core.security import validate_password_strength
from modules.auth.types import LoginMethod


def _require_matching(data: object, field: str, confirm_field: str) -> object:
    """Runs pre-field-parsing so a mismatch is reported before password
    strength is even checked — telling the user one of two differing
    values is weak is moot until they agree in the first place."""
    if isinstance(data, dict) and data.get(field) != data.get(confirm_field):
        raise ValueError("Passwords do not match")
    return data


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID7
    email: EmailStr
    first_name: str
    last_name: str
    profile_picture: str | None
    login_method: LoginMethod
    email_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    detail: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def passwords_match(cls, data: object) -> object:
        return _require_matching(data, "password", "confirm_password")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    access_expires_at: datetime


class LogoutRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResendCodeRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResetTokenResponse(BaseModel):
    reset_token: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str
    confirm_new_password: str

    @model_validator(mode="before")
    @classmethod
    def passwords_match(cls, data: object) -> object:
        return _require_matching(data, "new_password", "confirm_new_password")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @model_validator(mode="before")
    @classmethod
    def passwords_match(cls, data: object) -> object:
        return _require_matching(data, "new_password", "confirm_new_password")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    profile_picture: str | None = None
