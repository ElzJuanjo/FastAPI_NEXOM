"""
Entidades AgentConfig y AgentTask.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Integer, Numeric, String, Boolean, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, AgentType, AIProvider, StepStatus


class AgentConfig(UUIDPk, TimestampMixin, Base):
    __tablename__ = "agent_configs"

    organization_id:  Mapped[str]        = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    agent_type:       Mapped[AgentType]  = mapped_column(Enum(AgentType), nullable=False)
    ai_provider:      Mapped[AIProvider] = mapped_column(Enum(AIProvider), nullable=False)
    model_version:    Mapped[str]        = mapped_column(String(100), nullable=False)
    is_enabled:       Mapped[bool]       = mapped_column(Boolean, default=True, nullable=False)
    tasks_completed:  Mapped[int]        = mapped_column(Integer, default=0, nullable=False)
    tasks_total:      Mapped[int]        = mapped_column(Integer, default=0, nullable=False)
    config_params:    Mapped[Optional[dict]] = mapped_column(JSONB)

    organization: Mapped["Organization"] = relationship(back_populates="agent_configs")
    tasks:        Mapped[List["AgentTask"]] = relationship(back_populates="agent_config")

    __table_args__ = (
        UniqueConstraint("organization_id", "agent_type", name="uq_org_agent"),
    )


class AgentTask(UUIDPk, TimestampMixin, Base):
    __tablename__ = "agent_tasks"

    agent_config_id: Mapped[Optional[str]]      = mapped_column(UUID(as_uuid=False), ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True)
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

    agent_config: Mapped[Optional["AgentConfig"]] = relationship(back_populates="tasks")
    flow_step:    Mapped[Optional["FlowStep"]]    = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_agent_tasks_config_id",  "agent_config_id"),
        Index("ix_agent_tasks_status",     "status"),
        Index("ix_agent_tasks_created_at", "created_at"),
    )