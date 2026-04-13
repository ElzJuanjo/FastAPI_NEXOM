"""
NEXOM Domain Base: Base declarativa, Mixins y Enums compartidos.
"""

from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


# ---------------------------------------------------------------------------
# Base & helpers
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class UUIDPk:
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=new_uuid
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AuthProvider(str, enum.Enum):
    EMAIL = "email"
    GOOGLE = "google"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class PlanType(str, enum.Enum):
    FREE = "FREE"
    PLUS = "PLUS"
    VIP = "VIP"
    MVP = "MVP"


class BillingStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"


class AgentType(str, enum.Enum):
    GENERAL_ASSISTANT = "general_assistant"
    PRODUCT_SEARCH = "product_search"
    DROPI_CONNECTOR = "dropi_connector"
    STORE_DEV = "store_dev"
    LANDING_PAGE = "landing_page"
    IMAGE_GEN = "image_gen"
    VIDEO_GEN = "video_gen"
    ADS = "ads"
    BRANDING = "branding"
    COPYWRITING = "copywriting"
    CONVERSION_OPT = "conversion_opt"


class AIProvider(str, enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class AssetStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class FlowStatus(str, enum.Enum):
    INACTIVE = "inactive"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"


class CopyType(str, enum.Enum):
    AD = "ad"
    EMAIL = "email"
    SOCIAL = "social"
    HEADLINE = "headline"
    CTA = "cta"
    BODY = "body"


class AdPlatform(str, enum.Enum):
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    TIKTOK_ADS = "tiktok_ads"
    INSTAGRAM = "instagram"
    LANDING_PAGE = "landing_page"
    EMAIL_MARKETING = "email_marketing"


class LandingSectionType(str, enum.Enum):
    HERO = "hero"
    SOCIAL_PROOF = "social_proof"
    PROBLEM = "problem"
    SOLUTION = "solution"
    FEATURES = "features"
    BENEFITS = "benefits"
    TRANSFORMATION = "transformation"
    OFFER = "offer"
    TESTIMONIALS = "testimonials"
    PRICING = "pricing"
    FAQ = "faq"
    CTA = "cta"
    GALLERY = "gallery"
    CUSTOM = "custom"
    PRODUCT_GALLERY = "product_gallery"
    SPECS = "specs"
    VIDEO_EMBED = "video_embed"
    COMPARISON = "comparison"
    COUNTDOWN = "countdown"
    TRUST_BADGES = "trust_badges"
    BRAND_STORY = "brand_story"


class RecommendationStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    TESTING = "testing"
    REJECTED = "rejected"


class RecommendationImpact(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationEffort(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"