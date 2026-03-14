"""
DTOs para la ejecución de agentes.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExecuteAgentRequest(BaseModel):
    agent_config_id: str
    user_input: str = Field(min_length=1, max_length=10000)
    context: Optional[dict] = None


class ExecuteAgentResponse(BaseModel):
    task_id: str
    status: str
    content: Optional[str] = None
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    model: Optional[str] = None
    scraped_sources: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}