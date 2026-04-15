"""
DTOs para ejecución de Flows.
"""

from typing import Optional, Any

from pydantic import BaseModel, Field

from app.dto.product_dto import SelectableProductItem


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
    candidate_products: Optional[list[dict]] = None


class ExecuteFlowResponse(BaseModel):
    flow_id: str
    status: str
    total_steps: int
    completed_steps: int
    total_tokens: int = 0
    total_duration_ms: int = 0
    step_results: dict[str, StepResultSummary] = {}
    error: Optional[str] = None

    # ── Campos para manejar la pausa de selección de productos ──
    paused: bool = False
    pause_reason: Optional[str] = None
    pause_step_id: Optional[str] = None
    candidate_products: Optional[list[dict]] = None
    credits_consumed: int = 0
    credits_remaining: Optional[int] = None
    conversation_id: Optional[str] = None


class ResumeFlowWithSelectionRequest(BaseModel):
    """Body para /flows/{id}/resume-with-selection.

    Mínimo 1 producto (la UI debe obligar al usuario a elegir), máximo 20.
    """
    selected_products: list[SelectableProductItem] = Field(min_length=1, max_length=20)


class ResumeFlowWithSelectionResponse(BaseModel):
    flow_id: str
    status: str
    paused: bool = False
    total_steps: int = 0
    completed_steps: int = 0
    total_tokens: int = 0
    total_duration_ms: int = 0
    credits_consumed: int = 0
    credits_remaining: Optional[int] = None
    conversation_id: Optional[str] = None
    persisted_product_ids: list[str] = []
    skipped_names: list[str] = []
    step_results: dict[str, StepResultSummary] = {}
    error: Optional[str] = None
