from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database import BaseModel
from modules.auth.types import VerificationPurpose


class UserVerificationCode(BaseModel):
    __tablename__ = "user_verification_codes"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False)
    purpose: Mapped[VerificationPurpose] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at
