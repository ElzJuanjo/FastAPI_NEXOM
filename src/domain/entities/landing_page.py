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
from sqlalchemy.sql import func

from .base import Base, UUIDPk, TimestampMixin, LandingPageStatus, LandingSectionType


class LandingPage(UUIDPk, TimestampMixin, Base):
    __tablename__ = "landing_pages"

    organization_id: Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    brand_id:      Mapped[Optional[str]]  = mapped_column(UUID(as_uuid=False), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    name:          Mapped[str]           = mapped_column(String(255), nullable=False)
    campaign:      Mapped[Optional[str]] = mapped_column(String(255))
    status:        Mapped[LandingPageStatus]   = mapped_column(Enum(LandingPageStatus, name="landingpagestatus"), default=LandingPageStatus.DRAFT, nullable=False)
    published_url:    Mapped[Optional[str]] = mapped_column(String(512))
    published_at:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    template:         Mapped[Optional[str]] = mapped_column(String(50), default="modern", comment="CSS template: modern | minimal | bold | ecommerce | dark | elegant")
    seo_title:        Mapped[Optional[str]] = mapped_column(String(255))
    seo_description:  Mapped[Optional[str]] = mapped_column(Text)
    og_image:         Mapped[Optional[str]] = mapped_column(String(512))
    analytics_config: Mapped[Optional[dict]] = mapped_column(JSONB, comment='{"ga4_id":"G-XXX","meta_pixel_id":"XXX","gtm_id":"GTM-XXX"}')
    custom_css:       Mapped[Optional[str]]  = mapped_column(Text, comment="AI-generated bespoke CSS for this landing page")
    use_custom_css:   Mapped[bool]           = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"]          = relationship()
    brand:    Mapped["Brand"]                   = relationship(back_populates="landing_pages")
    sections: Mapped[List["LandingPageSection"]] = relationship(
        back_populates="landing_page",
        cascade="all, delete-orphan",
        order_by="LandingPageSection.order",
    )

    __table_args__ = (
        Index("ix_landing_pages_brand_id", "brand_id"),
        Index("ix_landing_pages_org_id", "organization_id"),
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
    image_url:       Mapped[Optional[str]]        = mapped_column(String(512), comment="Primary image URL for this section")
    images:          Mapped[Optional[list]]       = mapped_column(JSONB, comment="Array of image URLs for gallery-type sections")
    ab_group:        Mapped[Optional[str]]        = mapped_column(String(10), comment="A/B variant: 'a' or 'b'")

    landing_page: Mapped["LandingPage"] = relationship(back_populates="sections")

    __table_args__ = (
        UniqueConstraint("landing_page_id", "order", name="uq_landing_section_order"),
    )


class LandingLead(UUIDPk, Base):
    __tablename__ = "landing_leads"

    landing_page_id: Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("landing_pages.id", ondelete="CASCADE"), nullable=False)
    section_id:      Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    data:            Mapped[Optional[dict]] = mapped_column(JSONB, comment="Form submission fields as key-value pairs")
    created_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_landing_leads_lp_id", "landing_page_id"),
    )