"""
DTOs para Flow y FlowStep.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from domain.entities.base import AgentType


# ---------------------------------------------------------------------------
# FlowStep
# ---------------------------------------------------------------------------

# Valores válidos de agent_type extraídos del enum
_VALID_AGENT_TYPES = {e.value for e in AgentType}


class CreateFlowStepRequest(BaseModel):
    agent_type: str
    name: str = Field(min_length=1, max_length=255)
    order: int = Field(ge=1)
    depends_on_step_id: Optional[str] = None

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        if v not in _VALID_AGENT_TYPES:
            raise ValueError(
                f"agent_type '{v}' no es válido. "
                f"Valores permitidos: {', '.join(sorted(_VALID_AGENT_TYPES))}"
            )
        return v


class UpdateFlowStepRequest(BaseModel):
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class FlowStepResponse(BaseModel):
    id: str
    flow_id: str
    agent_type: str
    name: str
    order: int
    status: str
    depends_on_step_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------

class CreateFlowRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    context: Optional[dict] = None
    steps: list[CreateFlowStepRequest] = Field(min_length=2)

    @field_validator("steps")
    @classmethod
    def validate_min_steps(cls, v: list[CreateFlowStepRequest]) -> list[CreateFlowStepRequest]:
        if len(v) < 2:
            raise ValueError("Un flujo requiere al menos 2 pasos para orquestar agentes.")
        return v


class UpdateFlowRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    status: Optional[str] = None
    progress_pct: Optional[float] = Field(default=None, ge=0, le=100)
    context: Optional[dict] = None


class FlowResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    status: str
    progress_pct: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Optional[dict] = None
    steps: list[FlowStepResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class FlowListResponse(BaseModel):
    flows: list[FlowResponse]
