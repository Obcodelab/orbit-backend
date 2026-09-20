from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from core.types import Environment

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_PROJECT_ROOT / ".env", extra="ignore")

    ENVIRONMENT: Environment = Environment.LOCAL

    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    RESET_TOKEN_EXPIRE_MINUTES: int
    VERIFICATION_CODE_EXPIRE_MINUTES: int
    VERIFICATION_RESEND_COOLDOWN_SECONDS: int

    GOOGLE_SIGNIN_CLIENT_ID: str
    GOOGLE_SIGNIN_CLIENT_SECRET: str
    GOOGLE_SIGNIN_REDIRECT_URI: str

    BACKEND_CORS_ORIGINS: list[str]
    ALLOWED_HOSTS: list[str]

    RATE_LIMIT_AUTH: str
    RATE_LIMIT_DEFAULT: str


settings = Settings()  # type: ignore[call-arg]
