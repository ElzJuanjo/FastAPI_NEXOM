"""
Entidades Organization, Subscription y OrganizationMember.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base, UUIDPk, TimestampMixin, UserRole, BillingStatus


class Organization(UUIDPk, TimestampMixin, Base):
    __tablename__ = "organizations"

    name:                  Mapped[str]           = mapped_column(String(255), nullable=False)
    slug:                  Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    logo_url:              Mapped[Optional[str]] = mapped_column(String(512))
    plan_id:               Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("plans.id"), nullable=False)
    timezone:              Mapped[str]           = mapped_column(String(100), default="UTC", nullable=False)
    tasks_used_this_month: Mapped[int]           = mapped_column(Integer, default=0, nullable=False)
    billing_reset_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    plan:          Mapped["Plan"]                     = relationship(back_populates="organizations")
    subscription:  Mapped[Optional["Subscription"]]   = relationship(back_populates="organization", uselist=False)
    members:       Mapped[List["OrganizationMember"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    brands:        Mapped[List["Brand"]]              = relationship(back_populates="organization")
    products:      Mapped[List["Product"]]             = relationship(back_populates="organization")
    agent_configs: Mapped[List["AgentConfig"]]        = relationship(back_populates="organization")
    # TODO Sprint 6: descomentar cuando exista Flow
    # flows:         Mapped[List["Flow"]]               = relationship(back_populates="organization")
    
    __table_args__ = (
        Index("ix_organizations_slug", "slug"),
    )


class Subscription(UUIDPk, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    organization_id:        Mapped[str]             = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    stripe_subscription_id: Mapped[Optional[str]]   = mapped_column(String(255), unique=True)
    stripe_customer_id:     Mapped[Optional[str]]   = mapped_column(String(255))
    status:                 Mapped[BillingStatus]   = mapped_column(Enum(BillingStatus), nullable=False, default=BillingStatus.TRIALING)
    current_period_start:   Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancelled_at:           Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    payment_method_last4:   Mapped[Optional[str]]   = mapped_column(String(4))
    payment_method_brand:   Mapped[Optional[str]]   = mapped_column(String(20))

    organization: Mapped["Organization"] = relationship(back_populates="subscription")

    __table_args__ = (
        Index("ix_subscriptions_stripe_sub", "stripe_subscription_id"),
    )


class OrganizationMember(UUIDPk, TimestampMixin, Base):
    __tablename__ = "organization_members"

    organization_id: Mapped[str]       = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id:         Mapped[str]       = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role:            Mapped[UserRole]  = mapped_column(Enum(UserRole), default=UserRole.MEMBER, nullable=False)
    is_owner:        Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False,
                                            comment="Owner es el responsable de billing. Solo uno por org.")
    invited_by_id:   Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    joined_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    organization: Mapped["Organization"] = relationship(back_populates="members")
    user:         Mapped["User"]         = relationship(foreign_keys=[user_id], back_populates="organization_members")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        Index("ix_org_members_org_id", "organization_id"),
    )