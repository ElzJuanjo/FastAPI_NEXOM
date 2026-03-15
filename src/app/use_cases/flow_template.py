"""
Templates de Flows predefinidos.
Permite instanciar flujos completos con un solo endpoint.
"""

from __future__ import annotations

from domain.entities.flow import Flow, FlowStep
from domain.entities.base import FlowStatus, StepStatus, AgentType
from domain.repositories.flow_repository import FlowRepository


# ---------------------------------------------------------------------------
# Definición del ciclo completo
# ---------------------------------------------------------------------------

FULL_CYCLE_STEPS = [
    {
        "order": 1,
        "agent_type": "product_search",
        "name": "Búsqueda de producto ganador",
        "depends_on": None,
    },
    {
        "order": 2,
        "agent_type": "dropi_connector",
        "name": "Sincronización con Dropi",
        "depends_on": 1,
    },
    {
        "order": 3,
        "agent_type": "branding",
        "name": "Creación de Brand Book",
        "depends_on": 2,
    },
    {
        "order": 4,
        "agent_type": "copywriting",
        "name": "Generación de Copy",
        "depends_on": 3,
    },
    {
        "order": 5,
        "agent_type": "image_gen",
        "name": "Generación de imágenes",
        "depends_on": 3,  # paralelo con copy, ambos dependen de branding
    },
    {
        "order": 6,
        "agent_type": "ads",
        "name": "Creación de campañas de anuncios",
        "depends_on": 4,  # necesita copy
    },
    {
        "order": 7,
        "agent_type": "landing_page",
        "name": "Diseño de Landing Page",
        "depends_on": 4,  # necesita copy (paralelo con ads)
    },
    {
        "order": 8,
        "agent_type": "store_dev",
        "name": "Configuración de Tienda",
        "depends_on": 7,  # necesita landing
    },
    {
        "order": 9,
        "agent_type": "conversion_opt",
        "name": "Optimización de Conversión",
        "depends_on": 8,
    },
]

# Templates disponibles (extensible en el futuro)
FLOW_TEMPLATES = {
    "full_cycle": {
        "name_prefix": "Ciclo completo",
        "description": "Producto ganador → Dropi → Branding → Copy → Imágenes → Anuncios → Landing → Tienda → Conversión",
        "steps": FULL_CYCLE_STEPS,
    },
    "branding_launch": {
        "name_prefix": "Lanzamiento de marca",
        "description": "Branding → Copy → Imágenes → Landing",
        "steps": [
            {"order": 1, "agent_type": "branding", "name": "Creación de Brand Book", "depends_on": None},
            {"order": 2, "agent_type": "copywriting", "name": "Generación de Copy", "depends_on": 1},
            {"order": 3, "agent_type": "image_gen", "name": "Generación de imágenes", "depends_on": 1},
            {"order": 4, "agent_type": "landing_page", "name": "Diseño de Landing Page", "depends_on": 2},
        ],
    },
    "product_research": {
        "name_prefix": "Investigación de producto",
        "description": "Búsqueda → Dropi → Branding",
        "steps": [
            {"order": 1, "agent_type": "product_search", "name": "Búsqueda de producto ganador", "depends_on": None},
            {"order": 2, "agent_type": "dropi_connector", "name": "Sincronización con Dropi", "depends_on": 1},
            {"order": 3, "agent_type": "branding", "name": "Creación de Brand Book", "depends_on": 2},
        ],
    },
    "ads_campaign": {
        "name_prefix": "Campaña publicitaria",
        "description": "Copy → Imágenes → Anuncios → Landing",
        "steps": [
            {"order": 1, "agent_type": "copywriting", "name": "Generación de Copy", "depends_on": None},
            {"order": 2, "agent_type": "image_gen", "name": "Generación de imágenes", "depends_on": None},
            {"order": 3, "agent_type": "ads", "name": "Creación de campañas de anuncios", "depends_on": 1},
            {"order": 4, "agent_type": "landing_page", "name": "Diseño de Landing Page", "depends_on": 1},
        ],
    },
}


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class FlowTemplateNotFoundError(Exception):
    pass


class FlowFromTemplate:
    """Crea un Flow a partir de un template predefinido."""

    def __init__(self, flow_repo: FlowRepository) -> None:
        self._flow_repo = flow_repo

    def list_templates(self) -> list[dict]:
        """Lista todos los templates disponibles."""
        return [
            {
                "template_id": tid,
                "name": tmpl["name_prefix"],
                "description": tmpl["description"],
                "total_steps": len(tmpl["steps"]),
                "agents": [s["agent_type"] for s in tmpl["steps"]],
            }
            for tid, tmpl in FLOW_TEMPLATES.items()
        ]

    async def create_from_template(
        self,
        org_id: str,
        template_id: str,
        name: str | None = None,
        context: dict | None = None,
    ) -> Flow:
        """
        Crea un Flow con todos los steps del template.
        
        Args:
            org_id: ID de la organización
            template_id: ID del template (full_cycle, branding_launch, etc.)
            name: Nombre personalizado del flow (opcional)
            context: Contexto inicial del flow (marca, producto, etc.)
        """
        template = FLOW_TEMPLATES.get(template_id)
        if not template:
            available = ", ".join(FLOW_TEMPLATES.keys())
            raise FlowTemplateNotFoundError(
                f"Template '{template_id}' no encontrado. Disponibles: {available}"
            )

        flow_name = name or f"{template['name_prefix']} — {context.get('brand', 'NexOS')}" if context else template["name_prefix"]

        # Crear Flow
        flow = Flow(
            organization_id=org_id,
            name=flow_name,
            status=FlowStatus.INACTIVE,
            context=context or {},
        )
        flow = await self._flow_repo.create(flow)

        # Crear Steps — primero sin depends_on para obtener IDs
        step_id_by_order: dict[int, str] = {}
        steps_pending_deps: list[tuple[FlowStep, int | None]] = []

        for step_def in template["steps"]:
            step = FlowStep(
                flow_id=flow.id,
                agent_type=step_def["agent_type"],
                name=step_def["name"],
                order=step_def["order"],
                status=StepStatus.PENDING,
                depends_on_step_id=None,  # se asigna después
            )
            step = await self._flow_repo.add_step(step)
            step_id_by_order[step_def["order"]] = step.id
            steps_pending_deps.append((step, step_def.get("depends_on")))

        # Asignar dependencias ahora que tenemos todos los IDs
        for step, depends_on_order in steps_pending_deps:
            if depends_on_order and depends_on_order in step_id_by_order:
                step.depends_on_step_id = step_id_by_order[depends_on_order]
                await self._flow_repo.update_step(step)

        return flow