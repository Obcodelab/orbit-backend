from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import BaseModel
from modules.ai.types import AIMessageRole, CitationDict


class AIConversation(BaseModel):
    __tablename__ = "ai_conversations"

    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    messages: Mapped[list[AIMessage]] = relationship(
        "AIMessage", back_populates="conversation", cascade="all, delete-orphan"
    )


class AIMessage(BaseModel):
    __tablename__ = "ai_messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[AIMessageRole] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[CitationDict] | None] = mapped_column(JSON, nullable=True)

    conversation: Mapped[AIConversation] = relationship(
        "AIConversation", back_populates="messages"
    )
