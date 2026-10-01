from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import BaseModel


class AskIdempotencyKey(BaseModel):
    """A client-supplied key recorded once /ask completes — a replay with
    the same key returns the already-persisted message instead of
    re-running retrieval and paying for another Gemini call."""

    __tablename__ = "ask_idempotency_keys"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "key"),)
