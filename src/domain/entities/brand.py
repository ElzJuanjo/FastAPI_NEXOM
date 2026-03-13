"""
Entidad Brand — identidad de marca.
"""

from __future__ import annotations

from typing import Optional, List

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, AssetStatus


class Brand(UUIDPk, TimestampMixin, Base):
    __tablename__ = "brands"

    organization_id: Mapped[str]         = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name:            Mapped[str]         = mapped_column(String(255), nullable=False)
    tagline:         Mapped[Optional[str]] = mapped_column(String(512))
    status:          Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.DRAFT, nullable=False)

    color_palette:  Mapped[Optional[dict]] = mapped_column(JSONB,
        comment='{"primary": "#7C3AED", "secondary": "#3E1B48", "accent": "#F0ABFC", "background": null, "text": null}')
    typography:     Mapped[Optional[dict]] = mapped_column(JSONB,
        comment='{"heading_font": "Inter", "body_font": "Inter", "heading_weight": "700", "body_weight": "400"}')
    tones:          Mapped[Optional[list]] = mapped_column(ARRAY(String),
        comment='["Profesional", "Innovador", "Empatico", "Cientifico"]')
    key_messages:   Mapped[Optional[list]] = mapped_column(ARRAY(String),
        comment='["Formulas respaldadas por dermatologia clinica", "Resultados visibles en 14 dias"]')

    organization:  Mapped["Organization"]          = relationship(back_populates="brands")
    products:      Mapped[List["Product"]]         = relationship(back_populates="brand")
    # TODO Sprint 8+: descomentar cuando existan estas entidades
    # landing_pages: Mapped[List["LandingPage"]]     = relationship(back_populates="brand")
    # copy_assets:   Mapped[List["CopyAsset"]]       = relationship(back_populates="brand")
    # analyses:      Mapped[List["ConversionAnalysis"]] = relationship(back_populates="brand")