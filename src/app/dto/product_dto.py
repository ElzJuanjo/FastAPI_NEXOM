"""
DTOs para Product.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateProductRequest(BaseModel):
    brand_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(default=None, max_length=100)
    price_usd: Optional[float] = None
    image_url: Optional[str] = Field(default=None, max_length=512)
    dropi_product_id: Optional[str] = None
    extra_data: Optional[dict] = None


class UpdateProductRequest(BaseModel):
    brand_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(default=None, max_length=100)
    price_usd: Optional[float] = None
    image_url: Optional[str] = Field(default=None, max_length=512)
    is_active: Optional[bool] = None
    dropi_product_id: Optional[str] = None
    extra_data: Optional[dict] = None


class ProductResponse(BaseModel):
    id: str
    organization_id: str
    brand_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    sku: Optional[str] = None
    price_usd: Optional[float] = None
    image_url: Optional[str] = None
    is_active: bool
    dropi_product_id: Optional[str] = None
    extra_data: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    products: list[ProductResponse]


class ImportDropiRequest(BaseModel):
    dropi_product_id: str = Field(min_length=1, max_length=50)


class ImportDropiResponse(BaseModel):
    product: ProductResponse
    dropi_name: str
    dropi_stock: int = 0
    variations_count: int = 0