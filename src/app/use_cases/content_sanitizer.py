"""
Sanitiza el content del agente antes de entregarlo al usuario final.

Los agentes emiten bloques HTML-comment con JSON estructurado al final
de sus respuestas (<!--BRAND_JSON ... -->, <!--COPY_JSON ... -->,
<!--LANDING_JSON ... -->) para auto-persistencia interna.

Estos bloques son INFRAESTRUCTURA INTERNA y NO deben llegar al usuario.
Este módulo los elimina de forma segura sin alterar el contenido visible.
"""

from __future__ import annotations

import re

# Todos los patrones de bloques JSON internos que usan los agentes.
# Formato: <!-- TAG_JSON {..} --> o <!-- TAG_JSON [{..}] -->
_INTERNAL_JSON_PATTERN = re.compile(
    r'\s*<!--\s*(?:BRAND_JSON|COPY_JSON|LANDING_JSON)\s*[\[{].*?[\]}]\s*-->\s*',
    re.DOTALL,
)


def strip_internal_json(content: str | None) -> str:
    """
    Elimina todos los bloques <!--XXX_JSON ... --> del content.

    - Si el content es None o vacío, retorna string vacío.
    - Si no contiene bloques, retorna el content intacto (zero-cost).
    - Limpia whitespace trailing que quede después del strip.
    """
    if not content:
        return content or ""

    # Fast path: si no hay ningún marcador, no tocar nada
    if "<!--" not in content:
        return content

    cleaned = _INTERNAL_JSON_PATTERN.sub("", content)
    return cleaned.rstrip()
