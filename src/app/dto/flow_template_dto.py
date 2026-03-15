"""
DTOs para Flow Templates.
"""

from typing import Optional

from pydantic import BaseModel, Field


class FlowTemplateInfo(BaseModel):
    template_id: str
    name: str
    description: str
    total_steps: int
    agents: list[str]


class ListTemplatesResponse(BaseModel):
    templates: list[FlowTemplateInfo]


class CreateFlowFromTemplateRequest(BaseModel):
    template_id: str = Field(..., description="ID del template: full_cycle, branding_launch, product_research, ads_campaign")
    name: Optional[str] = Field(default=None, max_length=255, description="Nombre personalizado del flow")
    context: Optional[dict] = Field(default=None, description="Contexto inicial: brand, product, niche, market, etc.")
    auto_execute: bool = Field(default=False, description="Si True, ejecuta el flow inmediatamente después de crearlo")