from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CreateCreativeRequest(BaseModel):
    product_id: str
    agent_type: str = Field(..., description="image_gen o video_gen")
    platform: Optional[str] = None
    format: Optional[str] = Field(default=None, max_length=10)
    style: Optional[str] = Field(default=None, max_length=50)
    generation_prompt: Optional[str] = None
    generation_params: Optional[dict] = None


class UpdateCreativeRequest(BaseModel):
    status: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    duration_sec: Optional[float] = None


class CreativeResponse(BaseModel):
    id: str
    product_id: str
    agent_type: str
    platform: Optional[str] = None
    format: Optional[str] = None
    style: Optional[str] = None
    status: str
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    duration_sec: Optional[float] = None
    generation_prompt: Optional[str] = None
    generation_params: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreativeListResponse(BaseModel):
    creatives: list[CreativeResponse]