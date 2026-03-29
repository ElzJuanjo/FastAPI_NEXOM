from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CreateLandingSectionRequest(BaseModel):
    section_type: str
    title: Optional[str] = None
    body: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    order: int = Field(ge=1)
    is_visible: bool = True
    content: Optional[dict] = None


class UpdateLandingSectionRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    is_visible: Optional[bool] = None
    content: Optional[dict] = None


class LandingSectionResponse(BaseModel):
    id: str
    landing_page_id: str
    section_type: str
    title: Optional[str] = None
    body: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    order: int
    is_visible: bool
    content: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateLandingPageRequest(BaseModel):
    brand_id: Optional[str] = None
    name: str = Field(min_length=2, max_length=255)
    campaign: Optional[str] = None
    sections: Optional[list[CreateLandingSectionRequest]] = None


class UpdateLandingPageRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    campaign: Optional[str] = None
    status: Optional[str] = None
    brand_id: Optional[str] = None
    published_url: Optional[str] = None


class LandingPageResponse(BaseModel):
    id: str
    organization_id: str
    brand_id: Optional[str] = None
    name: str
    campaign: Optional[str] = None
    status: str
    published_url: Optional[str] = None
    published_at: Optional[datetime] = None
    sections: list[LandingSectionResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class LandingPageListResponse(BaseModel):
    landing_pages: list[LandingPageResponse]


class ReorderSectionsRequest(BaseModel):
    section_ids: list[str]