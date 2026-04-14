"""
Sanitiza el content del agente antes de entregarlo al usuario final.

Los agentes emiten bloques HTML-comment con JSON estructurado al final
de sus respuestas (<!--BRAND_JSON ... -->, <!--COPY_JSON ... -->,
<!--LANDING_JSON ... -->, <!--PRODUCT_JSON ... -->,
<!--SELECTABLE_PRODUCTS_JSON ... -->) para auto-persistencia interna
y para que el frontend pueda renderizar selectores (potenciales).

Estos bloques son INFRAESTRUCTURA INTERNA y NO deben llegar al usuario.
Este módulo los elimina de forma segura sin alterar el contenido visible.

NOTA: El extractor de selectable_products debe correr SOBRE EL CONTENIDO
RAW (antes de pasar por este sanitizer). Solo después se persiste el
content sanitizado en la BD.
"""

from __future__ import annotations

import re

# Todos los patrones de bloques JSON internos que usan los agentes.
# Formato: <!-- TAG_JSON {..} --> o <!-- TAG_JSON [{..}] -->
_INTERNAL_JSON_PATTERN = re.compile(
    r'\s*<!--\s*(?:BRAND_JSON|COPY_JSON|LANDING_JSON|PRODUCT_JSON|SELECTABLE_PRODUCTS_JSON)\s*[\[{].*?[\]}]\s*-->\s*',
    re.DOTALL,
)

# Fallback: bloques que el LLM dejó incompletos (sin cierre -->) o que
# remark-gfm pudo dañar al convertir "-->" en "⟶". Si el bloque empieza
# pero nunca cierra, también hay que removerlo para que no quede texto
# crudo de JSON visible.
_INTERNAL_JSON_OPEN_NO_CLOSE = re.compile(
    r'\s*<!--\s*(?:BRAND_JSON|COPY_JSON|LANDING_JSON|PRODUCT_JSON|SELECTABLE_PRODUCTS_JSON)\b[\s\S]*$',
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

    # Fast path: si no hay ningún marcador, no tocar nada
    if "<!--" not in content:
        return content

    # 1. Bloques bien formados: <!-- XXX_JSON [...] -->
    cleaned = _INTERNAL_JSON_PATTERN.sub("", content)

    # 2. Bloques abiertos sin cierre (LLM truncó o remark-gfm rompió "-->"):
    #    Si todavía queda un "<!--XXX_JSON" colgando hasta el final, lo cortamos.
    cleaned = _INTERNAL_JSON_OPEN_NO_CLOSE.sub("", cleaned)

    return cleaned.rstrip()
