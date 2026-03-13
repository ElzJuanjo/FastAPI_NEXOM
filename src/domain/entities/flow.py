"""
Entidades Flow y FlowStep — orquestación multi-agente.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    DateTime, Enum, Float, ForeignKey, Integer, String,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, FlowStatus, StepStatus, AgentType


class Flow(UUIDPk, TimestampMixin, Base):
    __tablename__ = "flows"

    organization_id:  Mapped[str]         = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name:             Mapped[str]         = mapped_column(String(255), nullable=False)
    status:           Mapped[FlowStatus]  = mapped_column(Enum(FlowStatus), default=FlowStatus.INACTIVE, nullable=False)
    progress_pct:     Mapped[float]       = mapped_column(Float, default=0.0)
    started_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    estimated_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    context:          Mapped[Optional[dict]]     = mapped_column(JSONB)

    organization: Mapped["Organization"]   = relationship(back_populates="flows")
    steps:        Mapped[List["FlowStep"]] = relationship(
        back_populates="flow",
        cascade="all, delete-orphan",
        order_by="FlowStep.order",
    )

    __table_args__ = (
        Index("ix_flows_org_status", "organization_id", "status"),
    )


class FlowStep(UUIDPk, TimestampMixin, Base):
    __tablename__ = "flow_steps"

    flow_id:            Mapped[str]         = mapped_column(UUID(as_uuid=False), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False)
    agent_type:         Mapped[AgentType]   = mapped_column(Enum(AgentType), nullable=False)
    name:               Mapped[str]         = mapped_column(String(255), nullable=False)
    order:              Mapped[int]         = mapped_column(Integer, nullable=False)
    status:             Mapped[StepStatus]  = mapped_column(Enum(StepStatus), default=StepStatus.PENDING, nullable=False)
    depends_on_step_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("flow_steps.id"), nullable=True)
    started_at:         Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    flow:  Mapped["Flow"]            = relationship(back_populates="steps")
    tasks: Mapped[List["AgentTask"]] = relationship(back_populates="flow_step")

    __table_args__ = (
        UniqueConstraint("flow_id", "order", name="uq_flow_step_order"),
        Index("ix_flow_steps_flow_id", "flow_id"),
    )