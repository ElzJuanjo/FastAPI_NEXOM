"""
DTOs para AgentTask (historial de ejecuciones).
AgentConfig ya no existe — los agentes son globales.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# AgentTask
# ---------------------------------------------------------------------------

class AgentTaskResponse(BaseModel):
    id: str
    organization_id: str
    agent_type: str
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
