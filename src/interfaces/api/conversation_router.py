"""
Endpoints de conversaciones — historial de chat multi-turn con agentes.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from infra.config.database import get_session
from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

from domain.entities.conversation import Conversation, ConversationMessage
from domain.entities.organization import Organization
from app.dto.conversation_dto import (
    ConversationResponse, ConversationDetailResponse, ConversationListResponse,
    ConversationMessageResponse, SendMessageRequest, SendMessageResponse,
    UpdateConversationRequest,
)
from app.dto.orchestrator_dto import OrchestratorResponse
from app.orchestration.orchestrator import run_orchestrator
from app.agents.credit_costs import get_credit_cost, ROUTER_CREDIT_COST
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org, get_current_org_id

from fastapi.responses import StreamingResponse
from infra.events.progress import ProgressEmitter, ProgressEvent
from app.use_cases.content_sanitizer import strip_internal_json
import asyncio
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

# Máximo de mensajes a enviar como contexto al LLM
MAX_CONTEXT_MESSAGES = 50


# ── List conversations ───────────────────────────────────────────────────────

@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    archived: bool = Query(default=False),
    limit: int = Query(default=30, le=100),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Lista conversaciones del usuario, ordenadas por última actividad."""
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.organization_id == org_id,
            Conversation.is_archived == archived,
            Conversation.deleted_at.is_(None),
        )
        .order_by(Conversation.last_message_at.desc().nullslast())
        .limit(limit)
    )
    result = await session.execute(stmt)
    convos = list(result.scalars().all())
    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in convos]
    )


# ── Get conversation with messages ───────────────────────────────────────────

@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Obtiene una conversación con todos sus mensajes."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    convo = result.scalar_one_or_none()

    if not convo:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    return ConversationDetailResponse.model_validate(convo)


# ── Send message (the main endpoint) ────────────────────────────────────────

@router.post("/send/stream")
@limiter.limit("15/minute")
async def send_message_stream(
    request: Request,
    body: SendMessageRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Envía un mensaje con streaming SSE de progreso."""
    plan = organization.plan
    org_id = str(organization.id)

    # Validar créditos
    remaining = plan.max_credits_per_month - organization.credits_used_this_month
    if remaining < 1:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Insufficient credits")

    emitter = ProgressEmitter()

    async def generate():
        import time
        _start_time = time.time()

        try:
            # Obtener o crear conversación
            if body.conversation_id:
                stmt = (
                    select(Conversation)
                    .options(selectinload(Conversation.messages))
                    .where(Conversation.id == body.conversation_id, Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
                )
                result = await session.execute(stmt)
                conversation = result.scalar_one_or_none()
                if not conversation:
                    yield emitter.to_sse_error("Conversation not found")
                    return
            else:
                title = body.content[:80] + ("..." if len(body.content) > 80 else "")
                conversation = Conversation(organization_id=org_id, user_id=user_id, title=title)
                session.add(conversation)
                await session.flush()

            # Guardar mensaje del usuario
            user_message = ConversationMessage(conversation_id=conversation.id, role="user", content=body.content)
            session.add(user_message)
            await session.flush()

            # Emit: starting
            yield emitter.to_sse(ProgressEvent(stage="routing", pct=10, message="Analyzing your request..."))

            # Build context
            history = conversation.messages if body.conversation_id else []
            context_messages = _build_context(history, body.content, MAX_CONTEXT_MESSAGES)

            # Run orchestrator with progress emitter
            # We run it in a task and consume emitter events
            result_holder = {}
            error_holder = {}

            async def run_orch():
                try:
                    r = await run_orchestrator(
                        user_input=body.content,
                        context={"conversation_history": context_messages},
                        progress_emitter=emitter,
                        force_agent=body.force_agent,
                    )
                    result_holder["data"] = r
                except Exception as e:
                    error_holder["error"] = str(e)
                finally:
                    await emitter.done()

            # Start orchestrator in background
            orch_task = asyncio.create_task(run_orch())

            # Stream progress events
            async for event in emitter:
                yield emitter.to_sse(event)

            # Wait for orchestrator to finish
            await orch_task

            if error_holder:
                yield emitter.to_sse_error(error_holder["error"])
                return

            result = result_holder.get("data", {})

            # Process images
            raw_images = result.get("images")
            s3_urls = []
            if raw_images and isinstance(raw_images, list):
                yield emitter.to_sse(ProgressEvent(stage="uploading", pct=85, message="Uploading images..."))

                normalized = []
                for img in raw_images:
                    if isinstance(img, str):
                        normalized.append(img)
                    elif isinstance(img, dict):
                        url = img.get("image_url", {}).get("url") or img.get("url", "")
                        if url:
                            normalized.append(url)

                base64_images = [img for img in normalized if img.startswith("data:") or len(img) > 500]
                if base64_images:
                    try:
                        from infra.tools.s3_client import upload_multiple_base64_images
                        s3_results = await upload_multiple_base64_images(base64_images, org_id=org_id)
                        s3_urls = [r["url"] for r in s3_results]

                        from app.use_cases.creative_persist import persist_creative
                        for s3_result in s3_results:
                            try:
                                await persist_creative(session=session, base64_image=s3_result["url"], org_id=org_id)
                            except Exception as e:
                                logger.error(f"Error auto-saving creative: {e}")
                    except Exception as e:
                        logger.error(f"Error uploading images: {e}")
                        s3_urls = normalized
                else:
                    s3_urls = normalized

            yield emitter.to_sse(ProgressEvent(stage="saving", pct=92, message="Saving to history..."))

            # Build response
            response_content_raw = result.get("content") or result.get("error") or ""
            response_content = strip_internal_json(response_content_raw)
            agent_type = result.get("selected_agent")

            total_credits = get_credit_cost(agent_type or "general_assistant")
            organization.credits_used_this_month += total_credits

            assistant_message = ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=response_content,
                agent_type=agent_type,
                meta_data={
                    "model": result.get("model"),
                    "tokens_used": result.get("tokens_used"),
                    "images": s3_urls if s3_urls else None,
                    "credits_consumed": total_credits,
                    "router_reasoning": result.get("router_reasoning"),
                },
            )
            session.add(assistant_message)

            conversation.message_count += 2
            conversation.last_message_at = datetime.now(timezone.utc)
            conversation.agent_type = agent_type

            # Agent task
            if agent_type:
                from domain.entities.agent import AgentTask
                try:
                    agent_task = AgentTask(
                        organization_id=org_id,
                        agent_type=agent_type,
                        status="completed" if not result.get("error") else "error",
                        input_payload={"user_input": body.content, "conversation_id": conversation.id},
                        output_payload={
                            "content": response_content[:500] if response_content else None,
                            "images": s3_urls if s3_urls else None,
                            "model": result.get("model"),
                        },
                        error_message=result.get("error"),
                        credits_used=total_credits,
                        duration_ms=int((time.time() - _start_time) * 1000),
                        started_at=datetime.now(timezone.utc),
                        finished_at=datetime.now(timezone.utc),
                    )
                    session.add(agent_task)
                except Exception as e:
                    logger.error(f"Error registering agent task: {e}")

            # Auto-persist landing page sections if agent is landing_page
            landing_page_id = None
            if agent_type == "landing_page" and response_content_raw and not result.get("error"):
                try:
                    from app.use_cases.landing_auto_persist import auto_persist_landing_sections
                    landing_page_id = await auto_persist_landing_sections(
                        session=session,
                        content=response_content_raw,
                        org_id=org_id,
                        brand_id=None,
                        conversation_id=conversation.id,
                    )
                except Exception as e:
                    logger.error(f"Error auto-persisting landing sections: {e}")
                    
            # Auto-persist brand identity if agent is branding
            if agent_type == "branding" and response_content_raw and not result.get("error"):
                try:
                    from app.use_cases.brand_auto_persist import auto_persist_brand_identity
                    await auto_persist_brand_identity(
                        session=session,
                        content=response_content_raw,
                        org_id=org_id,
                        conversation_id=conversation.id,
                    )
                except Exception as e:
                    logger.error(f"Error auto-persisting brand identity: {e}")
                    
            # Auto-persist copy assets if agent is copywriting or ads
            if agent_type in ("copywriting", "ads") and response_content_raw and not result.get("error"):
                try:
                    from app.use_cases.copy_auto_persist import auto_persist_copy_assets
                    await auto_persist_copy_assets(
                        session=session,
                        content=response_content_raw,
                        org_id=org_id,
                        brand_id=None,
                        conversation_id=conversation.id,
                    )
                except Exception as e:
                    logger.error(f"Error auto-persisting copy assets: {e}")

            await session.commit()

            credits_remaining = max(0, plan.max_credits_per_month - organization.credits_used_this_month)

            # Final SSE event with complete response
            done_payload = {
                "conversation_id": conversation.id,
                "message": {
                    "id": user_message.id,
                    "role": "user",
                    "content": user_message.content,
                    "agent_type": None,
                    "meta_data": None,
                    "created_at": str(user_message.created_at),
                },
                "response": {
                    "id": assistant_message.id,
                    "role": "assistant",
                    "content": assistant_message.content,
                    "agent_type": assistant_message.agent_type,
                    "meta_data": assistant_message.meta_data,
                    "created_at": str(assistant_message.created_at),
                },
                "credits_consumed": total_credits,
                "credits_remaining": credits_remaining,
            }

            yield emitter.to_sse_done(done_payload)

        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield emitter.to_sse_error(str(e))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    

@router.post("/send", response_model=SendMessageResponse)
@limiter.limit("15/minute")
async def send_message(
    request: Request,
    body: SendMessageRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Envía un mensaje y recibe respuesta del orquestador con contexto conversacional."""
    plan = organization.plan
    org_id = str(organization.id)

    # Validar créditos
    min_cost = ROUTER_CREDIT_COST + 1
    remaining = plan.max_credits_per_month - organization.credits_used_this_month
    if remaining < min_cost:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Créditos insuficientes: te quedan {remaining}/{plan.max_credits_per_month}.",
        )

    # Obtener o crear conversación
    conversation: Conversation | None = None
    if body.conversation_id:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == body.conversation_id,
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
        )
        result = await session.execute(stmt)
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
    else:
        # Nueva conversación — título del primer mensaje (truncado)
        title = body.content[:80] + ("..." if len(body.content) > 80 else "")
        conversation = Conversation(
            organization_id=org_id,
            user_id=user_id,
            title=title,
        )
        session.add(conversation)
        await session.flush()

    # Guardar mensaje del usuario
    user_message = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=body.content,
    )
    session.add(user_message)
    await session.flush()

    # Construir contexto conversacional para el LLM
    history = conversation.messages if body.conversation_id else []
    context_messages = _build_context(history, body.content, MAX_CONTEXT_MESSAGES)

    import time
    _start_time = time.time()
    
    # Llamar al orquestador
    try:
        result = await run_orchestrator(
            user_input=body.content,
            context={"conversation_history": context_messages},
            force_agent=body.force_agent,
        )
    except Exception as e:
        # Guardar error como mensaje del assistant
        error_msg = ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=f"Error: {str(e)}",
            meta_data={"error": True},
        )
        session.add(error_msg)
        conversation.message_count += 2
        conversation.last_message_at = datetime.now(timezone.utc)
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Error del orquestador: {str(e)}")

    # Normalizar imágenes si las hay
    raw_images = result.get("images")
    s3_urls = []
    if raw_images and isinstance(raw_images, list):
        normalized = []
        for img in raw_images:
            if isinstance(img, str):
                normalized.append(img)
            elif isinstance(img, dict):
                url = img.get("image_url", {}).get("url") or img.get("url", "")
                if url:
                    normalized.append(url)

        base64_images = [img for img in normalized if img.startswith("data:") or len(img) > 500]
        if base64_images:
            try:
                from infra.tools.s3_client import upload_multiple_base64_images
                s3_results = await upload_multiple_base64_images(base64_images, org_id=org_id)
                s3_urls = [r["url"] for r in s3_results]
                
                # Auto-guardar en creativos
                from app.use_cases.creative_persist import persist_creative
                for s3_result in s3_results:
                    try:
                        await persist_creative(
                            session=session,
                            base64_image=s3_result["url"],
                            org_id=org_id,
                        )
                    except Exception as e:
                        logger.error(f"Error auto-saving creative: {e}")
                        
            except Exception as e:
                logger.error(f"Error uploading images: {e}")
                s3_urls = normalized
        else:
            s3_urls = normalized

    # Construir respuesta del assistant
    response_content_raw = result.get("content") or result.get("error") or ""
    response_content = strip_internal_json(response_content_raw)
    agent_type = result.get("selected_agent") or body.agent_type

    # Cobrar créditos
    total_credits = get_credit_cost(agent_type or "general_assistant")
    organization.credits_used_this_month += total_credits

    # Guardar mensaje del assistant
    assistant_message = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=response_content,
        agent_type=agent_type,
        meta_data={
            "model": result.get("model"),
            "tokens_used": result.get("tokens_used"),
            "images": s3_urls if s3_urls else None,
            "credits_consumed": total_credits,
            "router_reasoning": result.get("router_reasoning"),
        },
    )
    session.add(assistant_message)

    # Actualizar conversación
    conversation.message_count += 2
    conversation.last_message_at = datetime.now(timezone.utc)
    conversation.agent_type = agent_type

    # Registrar en agent_tasks para actividad reciente
    if agent_type:
        from domain.entities.agent import AgentTask
        try:
            agent_task = AgentTask(
                organization_id=org_id,
                agent_type=agent_type,
                status="completed" if not result.get("error") else "error",
                input_payload={"user_input": body.content, "conversation_id": conversation.id},
                output_payload={
                    "content": response_content[:500] if response_content else None,
                    "images": s3_urls if s3_urls else None,
                    "model": result.get("model"),
                },
                error_message=result.get("error"),
                credits_used=total_credits,
                duration_ms=int((time.time() - _start_time) * 1000),
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
            session.add(agent_task)
        except Exception as e:
            logger.error(f"Error registering agent task: {e}")

    # Auto-persist landing page sections if agent is landing_page
    if agent_type == "landing_page" and response_content_raw and not result.get("error"):
        try:
            from app.use_cases.landing_auto_persist import auto_persist_landing_sections
            await auto_persist_landing_sections(
                session=session,
                content=response_content_raw,
                org_id=org_id,
                brand_id=None,
                conversation_id=conversation.id,
            )
        except Exception as e:
            logger.error(f"Error auto-persisting landing sections: {e}")

    # Auto-persist brand identity if agent is branding
    if agent_type == "branding" and response_content_raw and not result.get("error"):
        try:
            from app.use_cases.brand_auto_persist import auto_persist_brand_identity
            await auto_persist_brand_identity(
                session=session,
                content=response_content_raw,
                org_id=org_id,
                conversation_id=conversation.id,
            )
        except Exception as e:
            logger.error(f"Error auto-persisting brand identity: {e}")
            
    # Auto-persist copy assets if agent is copywriting or ads
    if agent_type in ("copywriting", "ads") and response_content_raw and not result.get("error"):
        try:
            from app.use_cases.copy_auto_persist import auto_persist_copy_assets
            await auto_persist_copy_assets(
                session=session,
                content=response_content_raw,
                org_id=org_id,
                brand_id=None,
                conversation_id=conversation.id,
            )
        except Exception as e:
            logger.error(f"Error auto-persisting copy assets: {e}")

    await session.commit()

    credits_remaining = max(0, plan.max_credits_per_month - organization.credits_used_this_month)

    return SendMessageResponse(
        conversation_id=conversation.id,
        message=ConversationMessageResponse.model_validate(user_message),
        response=ConversationMessageResponse.model_validate(assistant_message),
        credits_consumed=total_credits,
        credits_remaining=credits_remaining,
    )


# ── Update conversation ──────────────────────────────────────────────────────

@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    body: UpdateConversationRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
        Conversation.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    if body.title is not None:
        convo.title = body.title
    if body.is_archived is not None:
        convo.is_archived = body.is_archived

    await session.commit()
    return ConversationResponse.model_validate(convo)


# ── Delete conversation ──────────────────────────────────────────────────────

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    )
    result = await session.execute(stmt)
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    await session.delete(convo)  # hard delete, cascade borra mensajes
    await session.commit()


# ── Helper: build context for LLM ───────────────────────────────────────────

def _build_context(messages: list, current_input: str, max_messages: int) -> list[dict]:
    """
    Construye el historial conversacional para enviar al LLM.
    Usa sliding window: toma los últimos N mensajes.
    """
    history = []
    recent = messages[-max_messages:] if len(messages) > max_messages else messages

    for msg in recent:
        history.append({
            "role": msg.role,
            "content": msg.content,
        })

    return history