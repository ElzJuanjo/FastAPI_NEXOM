"""
Endpoint del orquestador — punto de entrada principal de NexOS.
El usuario habla con el orquestador, y este decide qué agente usar.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dto.orchestrator_dto import OrchestratorRequest, OrchestratorResponse
from app.orchestration.orchestrator import run_orchestrator
from interfaces.dependencies.auth_dependencies import get_current_user_id

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


@router.post("", response_model=OrchestratorResponse)
async def orchestrate(
    body: OrchestratorRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = await run_orchestrator(
            user_input=body.user_input,
            context=body.context,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el orquestador: {str(e)}",
        )

    return OrchestratorResponse(**result)