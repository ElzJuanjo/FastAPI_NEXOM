from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CreateCreativeRequest(BaseModel):
    product_id: Optional[str] = None
    agent_type: str = Field(default="image_gen")
    style: Optional[str] = None
    format: Optional[str] = None
    platform: Optional[str] = None
    angle: Optional[str] = None
    generation_prompt: Optional[str] = None
    generation_params: Optional[dict] = None


class UpdateCreativeRequest(BaseModel):
    product_id: Optional[str] = None
    status: Optional[str] = None
    style: Optional[str] = None
    format: Optional[str] = None
    platform: Optional[str] = None
    angle: Optional[str] = None


class CreativeResponse(BaseModel):
    id: str
    organization_id: str
    product_id: Optional[str] = None
    agent_type: str
    status: str
    file_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    style: Optional[str] = None
    format: Optional[str] = None
    platform: Optional[str] = None
    angle: Optional[str] = None
    generation_prompt: Optional[str] = None
    generation_params: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreativeListResponse(BaseModel):
    creatives: list[CreativeResponse]