"""
DTOs para ejecución de Flows.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ExecuteFlowRequest(BaseModel):
    flow_id: str
    context: Optional[dict] = None
    reference_image_url: Optional[str] = Field(
        default=None,
        description="URL S3 de imagen de referencia para el flow (ej: para pasar a image_gen o como contexto visual)",
    )


class StepResultSummary(BaseModel):
    agent_type: Optional[str] = None
    status: Optional[str] = None
    content_preview: Optional[str] = None
    tokens: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


class ExecuteFlowResponse(BaseModel):
    flow_id: str
    status: str
    total_steps: int
    completed_steps: int
    total_tokens: int
    total_duration_ms: int
    step_results: dict[str, StepResultSummary]
    error: Optional[str] = None
