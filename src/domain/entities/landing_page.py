"""
Entidades LandingPage y LandingPageSection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, AssetStatus, LandingSectionType


class LandingPage(UUIDPk, TimestampMixin, Base):
    __tablename__ = "landing_pages"

    brand_id:      Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    name:          Mapped[str]           = mapped_column(String(255), nullable=False)
    campaign:      Mapped[Optional[str]] = mapped_column(String(255))
    status:        Mapped[AssetStatus]   = mapped_column(Enum(AssetStatus), default=AssetStatus.DRAFT, nullable=False)
    published_url: Mapped[Optional[str]] = mapped_column(String(512))
    published_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    brand:    Mapped["Brand"]                   = relationship(back_populates="landing_pages")
    sections: Mapped[List["LandingPageSection"]] = relationship(
        back_populates="landing_page",
        cascade="all, delete-orphan",
        order_by="LandingPageSection.order",
    )

    __table_args__ = (
        Index("ix_landing_pages_brand_id", "brand_id"),
    )


class LandingPageSection(UUIDPk, TimestampMixin, Base):
    __tablename__ = "landing_page_sections"

    landing_page_id: Mapped[str]                  = mapped_column(UUID(as_uuid=False), ForeignKey("landing_pages.id", ondelete="CASCADE"), nullable=False)
    section_type:    Mapped[LandingSectionType]   = mapped_column(Enum(LandingSectionType), nullable=False)
    title:           Mapped[Optional[str]]        = mapped_column(String(255))
    body:            Mapped[Optional[str]]        = mapped_column(Text)
    cta_text:        Mapped[Optional[str]]        = mapped_column(String(255))
    cta_url:         Mapped[Optional[str]]        = mapped_column(String(512))
    order:           Mapped[int]                  = mapped_column(Integer, nullable=False)
    is_visible:      Mapped[bool]                 = mapped_column(Boolean, default=True)
    content:         Mapped[Optional[dict]]       = mapped_column(JSONB)

    landing_page: Mapped["LandingPage"] = relationship(back_populates="sections")

    __table_args__ = (
        UniqueConstraint("landing_page_id", "order", name="uq_landing_section_order"),
    )