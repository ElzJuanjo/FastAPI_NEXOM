"""
DTOs para Flow y FlowStep.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# FlowStep
# ---------------------------------------------------------------------------

class CreateFlowStepRequest(BaseModel):
    agent_type: str
    name: str = Field(min_length=1, max_length=255)
    order: int = Field(ge=1)
    depends_on_step_id: Optional[str] = None


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
    steps: Optional[list[CreateFlowStepRequest]] = None


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