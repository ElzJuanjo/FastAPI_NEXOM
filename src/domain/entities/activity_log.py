"""
Entidad ActivityLog — registro inmutable de eventos del sistema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base, UUIDPk, AgentType


class ActivityLog(UUIDPk, Base):
    """
    No tiene updated_at ni deleted_at: los logs nunca se modifican ni se borran.
    Nota: en producción esta tabla será particionada por RANGE(created_at).
    """
    __tablename__ = "activity_logs"

    organization_id: Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    actor_user_id:   Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    agent_type:      Mapped[Optional[AgentType]] = mapped_column(Enum(AgentType))
    action:          Mapped[str]           = mapped_column(String(255), nullable=False)
    entity_type:     Mapped[Optional[str]] = mapped_column(String(100))
    entity_id:       Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    summary:         Mapped[Optional[str]] = mapped_column(Text)
    status:          Mapped[Optional[str]] = mapped_column(String(50))
    extra_data:      Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_activity_logs_org_created", "organization_id", "created_at"),
        Index("ix_activity_logs_entity",      "entity_type", "entity_id"),
    )