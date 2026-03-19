"""
DTOs para el orquestador.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrchestratorRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=10000)
    context: Optional[dict] = None
    force_agent: Optional[str] = Field(default=None, description="Forzar un agente específico: branding, copywriting, ads, etc. Si se omite, el router decide.")


class OrchestratorResponse(BaseModel):
    content: Optional[str] = None
    selected_agent: Optional[str] = None
    router_reasoning: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    scraped_sources: Optional[dict] = None
    dropi_data: Optional[dict] = None
    images: Optional[list[str]] = None
    image_count: Optional[int] = None
    error: Optional[str] = None
    credits_consumed: Optional[int] = None
    credits_remaining: Optional[int] = None
    