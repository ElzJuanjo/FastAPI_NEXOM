"""
DTOs para Brand.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateBrandRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    tagline: Optional[str] = Field(default=None, max_length=512)
    color_palette: Optional[dict] = None
    typography: Optional[dict] = None
    tones: Optional[list[str]] = None
    key_messages: Optional[list[str]] = None
    brand_identity: Optional[dict] = None


class UpdateBrandRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    tagline: Optional[str] = Field(default=None, max_length=512)
    status: Optional[str] = None
    color_palette: Optional[dict] = None
    typography: Optional[dict] = None
    tones: Optional[list[str]] = None
    key_messages: Optional[list[str]] = None
    brand_identity: Optional[dict] = None


class BrandResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    tagline: Optional[str] = None
    status: str
    color_palette: Optional[dict] = None
    typography: Optional[dict] = None
    tones: Optional[list[str]] = None
    key_messages: Optional[list[str]] = None
    brand_identity: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandListResponse(BaseModel):
    brands: list[BrandResponse]