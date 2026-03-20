"""
Entidad CreativeBatch — agrupa creativos generados en una sola ejecución.
"""

from __future__ import annotations

from typing import Optional, List

from sqlalchemy import (
    Enum, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, FlowStatus


class CreativeBatch(UUIDPk, TimestampMixin, Base):
    __tablename__ = "creative_batches"

    organization_id:  Mapped[str]            = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    product_id:       Mapped[Optional[str]]  = mapped_column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    name:             Mapped[str]            = mapped_column(String(255), nullable=False)
    status:           Mapped[FlowStatus]     = mapped_column(Enum(FlowStatus), default=FlowStatus.RUNNING, nullable=False)
    total_expected:   Mapped[int]            = mapped_column(Integer, default=0)
    total_generated:  Mapped[int]            = mapped_column(Integer, default=0)
    total_failed:     Mapped[int]            = mapped_column(Integer, default=0)
    credits_consumed: Mapped[int]            = mapped_column(Integer, default=0)
    config:           Mapped[Optional[dict]] = mapped_column(JSONB, comment="product_name, product_description, brand_palette, etc.")

    # Relaciones
    creatives: Mapped[List["Creative"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    organization: Mapped["Organization"] = relationship()
    product: Mapped[Optional["Product"]] = relationship()