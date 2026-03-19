"""
DTOs para Organizations, Plans y Members.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

class PlanResponse(BaseModel):
    id: str
    name: str
    plan_type: str
    max_credits_per_month: int
    max_agents: int
    has_api_access: bool
    price_monthly_usd: float
    price_yearly_usd: float

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    timezone: str = Field(default="UTC", max_length=100)


class UpdateOrganizationRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    logo_url: Optional[str] = Field(default=None, max_length=512)
    timezone: Optional[str] = Field(default=None, max_length=100)


class ChangePlanRequest(BaseModel):
    plan_type: str = Field(..., description="Tipo de plan: free, pro, enterprise")


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    timezone: str
    credits_used_this_month: int
    plan: PlanResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationListResponse(BaseModel):
    organizations: list[OrganizationResponse]
