"""
Entidades User y UserAuthProvider.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, String, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPk, TimestampMixin, AuthProvider


class User(UUIDPk, TimestampMixin, Base):
    __tablename__ = "users"

    email:       Mapped[str]           = mapped_column(String(255), unique=True, nullable=False)
    full_name:   Mapped[str]           = mapped_column(String(255), nullable=False)
    avatar_url:  Mapped[Optional[str]] = mapped_column(String(512))
    is_active:   Mapped[bool]          = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    
    referral_code:       Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    referred_by_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    notif_prefs: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Keys: email_task_complete, email_flow_error, email_recommendation, in_app_task_complete, in_app_flow_error"
    )

    auth_providers:       Mapped[List["UserAuthProvider"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    organization_members: Mapped[List["OrganizationMember"]] = relationship(back_populates="user", foreign_keys="OrganizationMember.user_id")

    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
    )


class UserAuthProvider(UUIDPk, TimestampMixin, Base):
    __tablename__ = "user_auth_providers"

    user_id:          Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider:         Mapped[AuthProvider]  = mapped_column(Enum(AuthProvider), nullable=False)
    provider_user_id: Mapped[Optional[str]] = mapped_column(String(255))
    provider_email:   Mapped[Optional[str]] = mapped_column(String(255))
    password_hash:    Mapped[Optional[str]] = mapped_column(String(255))
    access_token:     Mapped[Optional[str]] = mapped_column(Text)
    refresh_token:    Mapped[Optional[str]] = mapped_column(Text)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="auth_providers")

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_auth_provider"),
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user_id"),
    )