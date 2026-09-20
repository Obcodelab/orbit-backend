from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database import BaseModel
from core.types import TokenType


class BlacklistedToken(BaseModel):
    __tablename__ = "blacklisted_tokens"

    jti: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)
    token_type: Mapped[TokenType] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
