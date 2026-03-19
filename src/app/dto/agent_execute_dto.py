"""
DTOs para la ejecución de agentes.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExecuteAgentRequest(BaseModel):
    agent_type: str = Field(
        ...,
        description="Tipo de agente a ejecutar: product_search, dropi_connector, branding, copywriting, ads, landing_page, store_dev, image_gen, conversion_opt, general_assistant",
    )
    user_input: str = Field(min_length=1, max_length=10000)
    context: Optional[dict] = None


class ExecuteAgentResponse(BaseModel):
    task_id: str
    agent_type: str
    status: str
    content: Optional[str] = None
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    model: Optional[str] = None
    scraped_sources: Optional[dict] = None
    images: Optional[list[str]] = None
    image_count: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}
