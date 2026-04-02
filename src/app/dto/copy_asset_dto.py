from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CreateCopyAssetRequest(BaseModel):
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    copy_type: str
    platform: Optional[str] = None
    tone: Optional[str] = None
    content: str = Field(..., min_length=1)
    status: str = "draft"
    variations: Optional[list] = None


class UpdateCopyAssetRequest(BaseModel):
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=255)
    copy_type: Optional[str] = None
    platform: Optional[str] = None
    tone: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    variations: Optional[list] = None


class CopyAssetResponse(BaseModel):
    id: str
    organization_id: str
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    name: str
    copy_type: str
    platform: Optional[str] = None
    tone: Optional[str] = None
    content: str
    status: str
    variations: Optional[list] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CopyAssetListResponse(BaseModel):
    assets: list[CopyAssetResponse]