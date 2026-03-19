"""
Entidad Creative — assets visuales generados por agentes de IA.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    BigInteger, Enum, ForeignKey, Index, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, AgentType, AssetStatus


class Creative(UUIDPk, TimestampMixin, Base):
    __tablename__ = "creatives"

    # Vinculación opcional a producto
    product_id:         Mapped[Optional[str]]     = mapped_column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    organization_id:    Mapped[str]               = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Metadata de generación
    agent_type:         Mapped[AgentType]         = mapped_column(Enum(AgentType), nullable=False)
    status:             Mapped[AssetStatus]       = mapped_column(Enum(AssetStatus), default=AssetStatus.PENDING, nullable=False)
    generation_prompt:  Mapped[Optional[str]]     = mapped_column(Text)
    generation_params:  Mapped[Optional[dict]]    = mapped_column(JSONB, comment="angle, model, aspect_ratio, etc.")

    # Archivo en S3
    file_url:           Mapped[Optional[str]]     = mapped_column(String(512))
    s3_key:             Mapped[Optional[str]]     = mapped_column(String(512), comment="S3 object key for deletion")
    batch_id:           Mapped[Optional[str]]     = mapped_column(UUID(as_uuid=False), ForeignKey("creative_batches.id", ondelete="SET NULL"), nullable=True)
    file_size_bytes:    Mapped[Optional[int]]     = mapped_column(BigInteger)

    # Categorización
    style:              Mapped[Optional[str]]     = mapped_column(String(50), comment="lifestyle | editorial | product_only | ugc_style | flat_lay")
    format:             Mapped[Optional[str]]     = mapped_column(String(10), comment="1:1 | 16:9 | 4:5 | 9:16")
    platform:           Mapped[Optional[str]]     = mapped_column(String(100), comment="Instagram/Facebook Feed, Stories, etc.")
    angle:              Mapped[Optional[str]]     = mapped_column(String(50), comment="transformation | pain | social_proof | curiosity | authority")

    # Campos legacy (mantener por compatibilidad, no se usan en nuevo flujo)
    thumbnail_url:      Mapped[Optional[str]]     = mapped_column(String(512))

    # Relaciones
    product: Mapped[Optional["Product"]] = relationship(back_populates="creatives")
    organization: Mapped["Organization"] = relationship()
    batch: Mapped[Optional["CreativeBatch"]] = relationship(back_populates="creatives")

    __table_args__ = (
        Index("ix_creatives_product_status", "product_id", "status"),
    )