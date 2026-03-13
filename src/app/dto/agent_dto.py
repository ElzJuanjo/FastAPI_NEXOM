"""
DTOs para AgentConfig y AgentTask.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------

class CreateAgentConfigRequest(BaseModel):
    agent_type: str = Field(..., description="Tipo de agente: product_search, dropi_connector, store_dev, etc.")
    ai_provider: str = Field(..., description="Proveedor: openai, anthropic, google")
    model_version: str = Field(..., max_length=100, description="Ej: gpt-4o, claude-sonnet-4-20250514, gemini-pro")
    is_enabled: bool = True
    config_params: Optional[dict] = None


class UpdateAgentConfigRequest(BaseModel):
    model_version: Optional[str] = Field(default=None, max_length=100)
    is_enabled: Optional[bool] = None
    config_params: Optional[dict] = None


class AgentConfigResponse(BaseModel):
    id: str
    organization_id: str
    agent_type: str
    ai_provider: str
    model_version: str
    is_enabled: bool
    tasks_completed: int
    tasks_total: int
    config_params: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentConfigListResponse(BaseModel):
    agent_configs: list[AgentConfigResponse]


# ---------------------------------------------------------------------------
# AgentTask
# ---------------------------------------------------------------------------

class CreateAgentTaskRequest(BaseModel):
    agent_config_id: str
    input_payload: Optional[dict] = None


class AgentTaskResponse(BaseModel):
    id: str
    agent_config_id: Optional[str] = None
    flow_step_id: Optional[str] = None
    status: str
    input_payload: Optional[dict] = None
    output_payload: Optional[dict] = None
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskResponse]