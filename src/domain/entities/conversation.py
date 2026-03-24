"""
Entidades Conversation y ConversationMessage — historial de chat multi-turn.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base, UUIDPk, TimestampMixin


class Conversation(UUIDPk, TimestampMixin, Base):
    __tablename__ = "conversations"

    organization_id: Mapped[str]            = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id:         Mapped[str]            = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title:           Mapped[Optional[str]]  = mapped_column(String(255))
    agent_type:      Mapped[Optional[str]]  = mapped_column(String(50), comment="Último agente usado")
    is_archived:     Mapped[bool]           = mapped_column(Boolean, default=False, nullable=False)
    message_count:   Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[Optional["datetime"]] = mapped_column(DateTime(timezone=True))

    # Relaciones
    messages: Mapped[List["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )

    __table_args__ = (
        Index("ix_conversations_user_org", "user_id", "organization_id"),
        Index("ix_conversations_last_msg", "user_id", "last_message_at"),
    )


class ConversationMessage(UUIDPk, Base):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[str]            = mapped_column(UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role:            Mapped[str]            = mapped_column(String(20), nullable=False, comment="user | assistant | system")
    content:         Mapped[str]            = mapped_column(Text, nullable=False)
    agent_type:      Mapped[Optional[str]]  = mapped_column(String(50))
    meta_data:        Mapped[Optional[dict]] = mapped_column(JSONB, comment="tokens, model, images, credits, etc.")
    created_at:      Mapped["datetime"]     = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relación
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_conv_messages_conv_created", "conversation_id", "created_at"),
    )