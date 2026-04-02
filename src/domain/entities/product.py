"""
Entidad Product — productos gestionados por la plataforma.
"""

from __future__ import annotations

from typing import Optional, List

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin


class Product(UUIDPk, TimestampMixin, Base):
    __tablename__ = "products"

    organization_id:   Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    brand_id:          Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("brands.id"), nullable=True)
    name:              Mapped[str]           = mapped_column(String(255), nullable=False)
    description:       Mapped[Optional[str]] = mapped_column(Text)
    sku:               Mapped[Optional[str]] = mapped_column(String(100))
    price_usd:         Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    image_url:         Mapped[Optional[str]] = mapped_column(String(512))
    is_active:         Mapped[bool]          = mapped_column(Boolean, default=True)
    dropi_product_id:  Mapped[Optional[str]] = mapped_column(String(255))
    extra_data:        Mapped[Optional[dict]] = mapped_column(JSONB)

    organization: Mapped["Organization"]   = relationship(back_populates="products")
    brand:        Mapped[Optional["Brand"]] = relationship(back_populates="products")
    creatives:    Mapped[List["Creative"]]  = relationship(back_populates="product")
    copy_assets:  Mapped[List["CopyAsset"]]  = relationship(back_populates="product")

    __table_args__ = (
        Index("ix_products_org_id",    "organization_id"),
        Index("ix_products_dropi_id",  "dropi_product_id"),
    )