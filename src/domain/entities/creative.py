"""
Entidad Creative — assets visuales (imágenes y videos) generados por Gemini.
"""

from __future__ import annotations

from typing import Optional, List

from sqlalchemy import (
    BigInteger, Enum, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, AgentType, AdPlatform, AssetStatus


class Creative(UUIDPk, TimestampMixin, Base):
    __tablename__ = "creatives"

    product_id:         Mapped[str]              = mapped_column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    agent_type:         Mapped[AgentType]         = mapped_column(Enum(AgentType), nullable=False)
    platform:           Mapped[Optional[AdPlatform]] = mapped_column(Enum(AdPlatform))
    format:             Mapped[Optional[str]]     = mapped_column(String(10), comment="1:1 | 16:9 | 4:5 | 9:16")
    style:              Mapped[Optional[str]]     = mapped_column(String(50), comment="minimalist | editorial | lifestyle | product_only")
    status:             Mapped[AssetStatus]       = mapped_column(Enum(AssetStatus), default=AssetStatus.PENDING, nullable=False)
    file_url:           Mapped[Optional[str]]     = mapped_column(String(512))
    thumbnail_url:      Mapped[Optional[str]]     = mapped_column(String(512))
    file_size_bytes:    Mapped[Optional[int]]     = mapped_column(BigInteger)
    width_px:           Mapped[Optional[int]]     = mapped_column(Integer)
    height_px:          Mapped[Optional[int]]     = mapped_column(Integer)
    duration_sec:       Mapped[Optional[float]]   = mapped_column(Float)
    generation_prompt:  Mapped[Optional[str]]     = mapped_column(Text)
    generation_params:  Mapped[Optional[dict]]    = mapped_column(JSONB)

    product: Mapped["Product"] = relationship(back_populates="creatives")

    __table_args__ = (
        Index("ix_creatives_product_status", "product_id", "status"),
    )