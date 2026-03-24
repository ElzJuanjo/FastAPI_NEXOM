"""
DTOs para AgentTask (historial de ejecuciones).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AgentTaskResponse(BaseModel):
    id: str
    organization_id: str
    agent_type: str
    flow_step_id: Optional[str] = None
    status: str
    input_payload: Optional[dict] = None
    output_payload: Optional[dict] = None
    error_message: Optional[str] = None
    credits_used: Optional[int] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskResponse]