"""
Entidad AgentTask — registro de ejecuciones de agentes.
Los agentes son globales (definidos en app/agents/), no configurables per-org.
AgentTask registra cada ejecución con su agent_type y organization_id.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Integer, Numeric, String, Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, AgentType, StepStatus


class AgentTask(UUIDPk, TimestampMixin, Base):
    __tablename__ = "agent_tasks"

    organization_id: Mapped[str]                = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    agent_type:      Mapped[AgentType]          = mapped_column(Enum(AgentType), nullable=False)
    flow_step_id:    Mapped[Optional[str]]      = mapped_column(UUID(as_uuid=False), ForeignKey("flow_steps.id", ondelete="SET NULL"), nullable=True)
    status:          Mapped[StepStatus]         = mapped_column(Enum(StepStatus), default=StepStatus.PENDING, nullable=False)
    input_payload:   Mapped[Optional[dict]]     = mapped_column(JSONB)
    output_payload:  Mapped[Optional[dict]]     = mapped_column(JSONB)
    error_message:   Mapped[Optional[str]]      = mapped_column(Text)
    tokens_used:     Mapped[Optional[int]]      = mapped_column(Integer)
    cost_usd:        Mapped[Optional[float]]    = mapped_column(Numeric(10, 6))
    started_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms:     Mapped[Optional[int]]      = mapped_column(Integer)

    organization: Mapped["Organization"] = relationship(back_populates="agent_tasks")
    flow_step:    Mapped[Optional["FlowStep"]] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_agent_tasks_org_id",     "organization_id"),
        Index("ix_agent_tasks_agent_type", "agent_type"),
        Index("ix_agent_tasks_status",     "status"),
        Index("ix_agent_tasks_created_at", "created_at"),
    )
