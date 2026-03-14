"""
Entidades ConversionAnalysis y OptimizationRecommendation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Index, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import (
    Base, UUIDPk, TimestampMixin,
    RecommendationStatus, RecommendationImpact, RecommendationEffort,
)


class ConversionAnalysis(UUIDPk, TimestampMixin, Base):
    __tablename__ = "conversion_analyses"

    brand_id:                    Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    analyzed_at:                 Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    aov_usd:                     Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    aov_target_usd:              Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    cltv_usd:                    Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    cltv_target_usd:             Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    conversion_rate_pct:         Mapped[Optional[float]] = mapped_column(Float)
    conversion_rate_target_pct:  Mapped[Optional[float]] = mapped_column(Float)
    repurchase_rate_pct:         Mapped[Optional[float]] = mapped_column(Float)
    repurchase_rate_target_pct:  Mapped[Optional[float]] = mapped_column(Float)
    cart_abandonment_pct:        Mapped[Optional[float]] = mapped_column(Float)
    cart_abandonment_target_pct: Mapped[Optional[float]] = mapped_column(Float)
    upsell_rate_pct:             Mapped[Optional[float]] = mapped_column(Float)
    upsell_rate_target_pct:      Mapped[Optional[float]] = mapped_column(Float)
    potential_revenue_usd:       Mapped[Optional[float]] = mapped_column(Numeric(12, 2))

    brand:           Mapped["Brand"]                          = relationship(back_populates="analyses")
    recommendations: Mapped[List["OptimizationRecommendation"]] = relationship(back_populates="analysis")

    __table_args__ = (
        Index("ix_conv_analyses_brand_date", "brand_id", "analyzed_at"),
    )


class OptimizationRecommendation(UUIDPk, TimestampMixin, Base):
    __tablename__ = "optimization_recommendations"

    analysis_id:          Mapped[str]                    = mapped_column(UUID(as_uuid=False), ForeignKey("conversion_analyses.id", ondelete="CASCADE"), nullable=False)
    title:                Mapped[str]                    = mapped_column(String(255), nullable=False)
    description:          Mapped[Optional[str]]          = mapped_column(Text)
    impact:               Mapped[RecommendationImpact]   = mapped_column(Enum(RecommendationImpact), nullable=False)
    effort:               Mapped[RecommendationEffort]   = mapped_column(Enum(RecommendationEffort), nullable=False)
    status:               Mapped[RecommendationStatus]   = mapped_column(Enum(RecommendationStatus), default=RecommendationStatus.PENDING, nullable=False)
    ab_test_active:       Mapped[bool]                   = mapped_column(Boolean, default=False)
    applied_at:           Mapped[Optional[datetime]]     = mapped_column(DateTime(timezone=True))
    expected_uplift_pct:  Mapped[Optional[float]]        = mapped_column(Float)
    actual_uplift_pct:    Mapped[Optional[float]]        = mapped_column(Float)

    analysis: Mapped["ConversionAnalysis"] = relationship(back_populates="recommendations")

    __table_args__ = (
        Index("ix_opt_rec_analysis_status", "analysis_id", "status"),
    )