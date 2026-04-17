"""
Límites de recursos por organización — módulo centralizado.

Controla la cantidad máxima de cada tipo de recurso que una organización
puede tener activo (sin soft-delete). Además gestiona la rotación automática
de conversations y agent_tasks cuando se acercan a su tope.

Uso:
    from app.use_cases.resource_limits import check_resource_limit, cleanup_if_needed

    # En CRUDs y auto-persist (lanza error si se excede):
    await check_resource_limit(session, org_id, "brands")

    # En creación de conversations y agent_tasks (rota sin error):
    await cleanup_if_needed(session, org_id, "conversations")
"""

from __future__ import annotations

import logging
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Límites por recurso ──────────────────────────────────────────────────────

RESOURCE_LIMITS: dict[str, int] = {
    "brands":        30,
    "products":      400,
    "copy_assets":   500,
    "creatives":     300,
    "landing_pages": 50,
    "flows":         30,
    "conversations": 500,
    "agent_tasks":   5000,
}

# Recursos con rotación automática (no bloquean, borran los más viejos)
# (resource_key, threshold_para_limpiar, cantidad_a_borrar)
AUTO_ROTATE_CONFIG: dict[str, tuple[int, int]] = {
    "conversations": (490, 50),   # al llegar a 490, borrar las 50 más antiguas
    "agent_tasks":   (4900, 500), # al llegar a 4900, borrar los 500 más antiguos
}


# ── Excepciones ──────────────────────────────────────────────────────────────

class ResourceLimitExceededError(Exception):
    """Se excedió el límite de un recurso."""

    def __init__(self, resource: str, current: int, limit: int):
        self.resource = resource
        self.current = current
        self.limit = limit
        super().__init__(
            f"Límite alcanzado: tienes {current}/{limit} {_RESOURCE_LABELS.get(resource, resource)}. "
            f"Elimina algunos para poder crear más."
        )


# ── Labels para mensajes legibles ────────────────────────────────────────────

_RESOURCE_LABELS: dict[str, str] = {
    "brands":        "marcas",
    "products":      "productos",
    "copy_assets":   "copys",
    "creatives":     "creativos",
    "landing_pages": "landing pages",
    "flows":         "flujos",
    "conversations": "conversaciones",
    "agent_tasks":   "tareas de agente",
}


# ── Mapping recurso → entidad SQLAlchemy ─────────────────────────────────────

def _get_entity(resource: str):
    """Retorna la clase SQLAlchemy correspondiente al recurso."""
    if resource == "brands":
        from domain.entities.brand import Brand
        return Brand
    elif resource == "products":
        from domain.entities.product import Product
        return Product
    elif resource == "copy_assets":
        from domain.entities.copy_asset import CopyAsset
        return CopyAsset
    elif resource == "creatives":
        from domain.entities.creative import Creative
        return Creative
    elif resource == "landing_pages":
        from domain.entities.landing_page import LandingPage
        return LandingPage
    elif resource == "flows":
        from domain.entities.flow import Flow
        return Flow
    elif resource == "conversations":
        from domain.entities.conversation import Conversation
        return Conversation
    elif resource == "agent_tasks":
        from domain.entities.agent import AgentTask
        return AgentTask
    else:
        raise ValueError(f"Recurso desconocido: {resource}")


# ── Funciones para contar (respetando soft-delete) ───────────────────────────

def _has_deleted_at(entity) -> bool:
    """Verifica si la entidad tiene columna deleted_at."""
    return hasattr(entity, "deleted_at")


async def count_resources(session: AsyncSession, org_id: str, resource: str) -> int:
    """Cuenta registros activos de un recurso para una organización."""
    entity = _get_entity(resource)
    stmt = (
        select(func.count())
        .select_from(entity)
        .where(entity.organization_id == org_id)
    )
    if _has_deleted_at(entity):
        stmt = stmt.where(entity.deleted_at.is_(None))

    result = await session.execute(stmt)
    return result.scalar() or 0


# ── Check de límite (para recursos con bloqueo) ─────────────────────────────

async def check_resource_limit(
    session: AsyncSession,
    org_id: str,
    resource: str,
) -> None:
    """
    Verifica que la organización no haya alcanzado el límite del recurso.
    Lanza ResourceLimitExceededError si se excede.

    Usar en CRUDs manuales y auto-persist de: brands, products, copy_assets,
    creatives, landing_pages, flows.
    """
    limit = RESOURCE_LIMITS.get(resource)
    if limit is None:
        return  # Sin límite configurado

    current = await count_resources(session, org_id, resource)
    if current >= limit:
        raise ResourceLimitExceededError(resource, current, limit)


# ── Cleanup automático (para conversations y agent_tasks) ────────────────────

async def cleanup_if_needed(
    session: AsyncSession,
    org_id: str,
    resource: str,
) -> int:
    """
    Si el recurso está cerca de su tope, elimina los registros más antiguos.
    Retorna la cantidad de registros eliminados.

    Usar ANTES de crear nuevos registros de conversations y agent_tasks.
    No lanza error — simplemente rota los más viejos silenciosamente.
    """
    config = AUTO_ROTATE_CONFIG.get(resource)
    if config is None:
        return 0

    threshold, delete_count = config

    current = await count_resources(session, org_id, resource)
    if current < threshold:
        return 0

    entity = _get_entity(resource)

    # Subquery: IDs de los N más antiguos
    oldest_subquery = (
        select(entity.id)
        .where(entity.organization_id == org_id)
    )
    if _has_deleted_at(entity):
        oldest_subquery = oldest_subquery.where(entity.deleted_at.is_(None))

    oldest_subquery = (
        oldest_subquery
        .order_by(entity.created_at.asc())
        .limit(delete_count)
    )

    # Para conversations: hard delete (cascade borra messages)
    # Para agent_tasks: hard delete directo
    ids_result = await session.execute(oldest_subquery)
    ids_to_delete = [row[0] for row in ids_result.all()]

    if not ids_to_delete:
        return 0

    stmt = delete(entity).where(entity.id.in_(ids_to_delete))
    result = await session.execute(stmt)
    deleted = result.rowcount or 0

    logger.info(
        f"Auto-rotated {deleted} {resource} for org {org_id} "
        f"(was at {current}/{RESOURCE_LIMITS.get(resource, '?')})"
    )

    return deleted
