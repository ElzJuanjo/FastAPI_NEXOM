"""
Sanitiza el content del agente antes de entregarlo al usuario final.

Los agentes emiten bloques HTML-comment con JSON estructurado al final
de sus respuestas (<!--BRAND_JSON ... -->, <!--COPY_JSON ... -->,
<!--LANDING_JSON ... -->, <!--CANDIDATE_PRODUCTS_JSON ... -->) para
persistencia interna y para que el frontend pueda renderizar selectores.

Estos bloques son INFRAESTRUCTURA INTERNA y NO deben llegar al usuario.
Este módulo los elimina de forma segura sin alterar el contenido visible.

NOTA: Los extractores (extract_candidate_products, etc.) deben correr
SOBRE EL CONTENIDO RAW (antes de pasar por este sanitizer). Solo después
se persiste el content sanitizado en la BD.
"""

from __future__ import annotations

import re

# Todos los patrones de bloques JSON internos que usan los agentes.
# Formato: <!-- TAG_JSON {..} --> o <!-- TAG_JSON [{..}] -->
_INTERNAL_JSON_TAGS = (
    "BRAND_JSON",
    "COPY_JSON",
    "LANDING_JSON",
    "CANDIDATE_PRODUCTS_JSON",
)

_TAGS_GROUP = "|".join(_INTERNAL_JSON_TAGS)

_INTERNAL_JSON_PATTERN = re.compile(
    rf'\s*<!--\s*(?:{_TAGS_GROUP})\s*[\[{{].*?[\]}}]\s*-->\s*',
    re.DOTALL,
)

_INTERNAL_JSON_OPEN_NO_CLOSE = re.compile(
    rf'\s*<!--\s*(?:{_TAGS_GROUP})\b[\s\S]*$',
    re.DOTALL,
)


def strip_internal_json(content: str | None) -> str:
    """
    Elimina todos los bloques <!--XXX_JSON ... --> del content.

    - Si el content es None o vacío, retorna string vacío.
    - Si no contiene bloques, retorna el content intacto (zero-cost).
    - Limpia bloques bien formados y también bloques abiertos sin cierre
      (defensivo contra outputs truncados del LLM).
    - Limpia whitespace trailing que quede después del strip.
    """
    if not content:
        return content or ""

    if "<!--" not in content:
        return content

    cleaned = _INTERNAL_JSON_PATTERN.sub("", content)
    cleaned = _INTERNAL_JSON_OPEN_NO_CLOSE.sub("", cleaned)

    return cleaned.rstrip()
