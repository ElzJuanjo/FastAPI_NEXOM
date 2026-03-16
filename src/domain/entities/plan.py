"""
Entidad Plan — definición de planes de suscripción.
"""

from __future__ import annotations

from typing import Optional, List

from sqlalchemy import Boolean, Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, PlanType


class Plan(UUIDPk, TimestampMixin, Base):
    __tablename__ = "plans"

    name:                  Mapped[str]   = mapped_column(String(100), nullable=False)
    plan_type:             Mapped[PlanType] = mapped_column(Enum(PlanType), unique=True, nullable=False)
    max_credits_per_month: Mapped[int]   = mapped_column(Integer, nullable=False)
    max_agents:            Mapped[int]   = mapped_column(Integer, nullable=False)
    has_api_access:        Mapped[bool]  = mapped_column(Boolean, default=False, nullable=False)
    price_monthly_usd:     Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_yearly_usd:      Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    organizations: Mapped[List["Organization"]] = relationship(back_populates="plan")