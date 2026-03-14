"""
Entidad CopyAsset — contenido textual generado por el agente de Copywriting.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, CopyType, AdPlatform, AssetStatus


class CopyAsset(UUIDPk, TimestampMixin, Base):
    __tablename__ = "copy_assets"

    brand_id:   Mapped[str]               = mapped_column(UUID(as_uuid=False), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    name:       Mapped[str]               = mapped_column(String(255), nullable=False)
    copy_type:  Mapped[CopyType]          = mapped_column(Enum(CopyType), nullable=False)
    platform:   Mapped[Optional[AdPlatform]] = mapped_column(Enum(AdPlatform))
    tone:       Mapped[Optional[str]]     = mapped_column(String(100))
    content:    Mapped[str]               = mapped_column(Text, nullable=False)
    status:     Mapped[AssetStatus]       = mapped_column(Enum(AssetStatus), default=AssetStatus.DRAFT, nullable=False)
    variations: Mapped[Optional[list]]    = mapped_column(JSONB,
        comment='[{"content": "Variacion 1...", "order": 1}, {"content": "Variacion 2...", "order": 2}]')

    brand: Mapped["Brand"] = relationship(back_populates="copy_assets")

    __table_args__ = (
        Index("ix_copy_assets_brand_type", "brand_id", "copy_type"),
        Index("ix_copy_assets_status",     "status"),
    )