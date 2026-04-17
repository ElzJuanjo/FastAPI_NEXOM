"""
Auto-persistencia de Brand Identity desde output del agente de branding.

ESTRATEGIA V3 — JSON embebido:
El system prompt del branding agent le indica que emita un bloque
<!--BRAND_JSON {...} --> al final de su respuesta markdown.
Este módulo simplemente extrae ese JSON y lo persiste.

Fallback: si el bloque JSON no existe (respuestas parciales, continuaciones,
o si el agente no lo incluyó), se intenta un parsing heurístico básico.
"""

from __future__ import annotations

import re
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.brand import Brand
from domain.entities.base import AssetStatus

logger = logging.getLogger(__name__)


# ── Detection ────────────────────────────────────────────────────────────────

def is_brand_content(content: str) -> bool:
    """Detecta si el output del agente contiene un Brand Book."""
    if not content or len(content) < 300:
        return False

    # Fast path: JSON block present
    if "<!--BRAND_JSON" in content:
        return True

    # Heuristic: count brand-related section indicators
    indicators = 0
    patterns = [
        r'(?:color\s*palette|paleta\s*de\s*colore?s)',
        r'(?:typography|tipograf[ií]a)',
        r'(?:tone\s*of\s*voice|tono\s*de\s*voz)',
        r'(?:archetype|arquetipo)',
        r'(?:key\s*messages|mensajes\s*clave)',
        r'#[0-9A-Fa-f]{6}',
        r'(?:misi[oó]n|mission)',
    ]
    for p in patterns:
        if re.search(p, content, re.IGNORECASE):
            indicators += 1

    return indicators >= 4


# ── JSON Extraction (primary) ────────────────────────────────────────────────

def _extract_brand_json(content: str) -> dict | None:
    """
    Extract the structured JSON from <!--BRAND_JSON {...} --> comment block.
    Returns parsed dict or None if not found / invalid.
    """
    match = re.search(
        r'<!--\s*BRAND_JSON\s*(\{.*?\})\s*-->',
        content,
        re.DOTALL
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        if isinstance(data, dict) and data.get("name"):
            return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse BRAND_JSON block: {e}")

    return None


# ── Heuristic Fallback (secondary) ───────────────────────────────────────────

def _fallback_parse(content: str) -> dict | None:
    """
    Fallback heuristic parser for when the agent doesn't include BRAND_JSON.
    Extracts minimal data: name, colors, and basic identity.
    """
    result: dict = {}

    # Name: bold text after "nombre" label
    name_match = re.search(
        r'(?:nombre|brand\s*name)[^\n]*\n\s*\*{2}([^*\n]+)\*{2}',
        content, re.IGNORECASE
    )
    if name_match:
        result["name"] = name_match.group(1).strip()[:255]

    # Colors: extract HEX values near role keywords
    palette = {}
    for role_re, key in [
        (r'primari[oa]|primary', "primary"),
        (r'secundari[oa]|secondary', "secondary"),
        (r'acento|accent', "accent"),
        (r'fondo|background', "background"),
        (r'texto|text(?:o)?', "text"),
    ]:
        m = re.search(
            rf'(?:{role_re})[\s\S]{{0,150}}?(#[0-9A-Fa-f]{{6}})',
            content, re.IGNORECASE
        )
        if m:
            palette[key] = m.group(1).upper()
    if len(palette) >= 2:
        result["color_palette"] = palette

    return result if result else None


# ── Main Parser ──────────────────────────────────────────────────────────────

def parse_brand_identity(content: str) -> dict | None:
    """
    Parse brand identity from agent output.
    Primary: extract structured JSON block.
    Fallback: heuristic extraction of basic fields.
    """
    data = _extract_brand_json(content)
    if data:
        return _normalize_brand_data(data)

    logger.info("BRAND_JSON block not found, using fallback parser")
    return _fallback_parse(content)


def _normalize_brand_data(data: dict) -> dict:
    """Normalize and validate the JSON data from the agent."""
    result: dict = {}

    if data.get("name"):
        result["name"] = str(data["name"])[:255]

    if data.get("tagline"):
        result["tagline"] = str(data["tagline"])[:512]

    # Color palette
    cp = data.get("color_palette")
    if isinstance(cp, dict):
        valid_palette = {}
        for key in ("primary", "secondary", "accent", "background", "text"):
            val = cp.get(key)
            if val and isinstance(val, str) and re.match(r'^#[0-9A-Fa-f]{6}$', val):
                valid_palette[key] = val.upper()
        if len(valid_palette) >= 2:
            result["color_palette"] = valid_palette

    # Typography
    tp = data.get("typography")
    if isinstance(tp, dict):
        valid_typo = {}
        for key in ("heading_font", "body_font", "ui_font"):
            val = tp.get(key)
            if val and isinstance(val, str) and 2 < len(val) < 50:
                valid_typo[key] = val
        if valid_typo:
            result["typography"] = valid_typo

    # Tones
    tones = data.get("tones")
    if isinstance(tones, list):
        result["tones"] = [str(t).strip() for t in tones if t and len(str(t).strip()) > 1][:10]

    # Key messages
    msgs = data.get("key_messages")
    if isinstance(msgs, list):
        result["key_messages"] = [str(m).strip() for m in msgs if m and len(str(m).strip()) > 5][:10]

    # Brand identity (extended)
    identity = {}
    for field in ("archetype", "purpose", "mission", "vision", "logo_concept"):
        val = data.get(field)
        if val and isinstance(val, str) and len(val) > 5:
            identity[field] = val[:500]

    values = data.get("values")
    if isinstance(values, list):
        identity["values"] = [str(v).strip() for v in values if v and len(str(v).strip()) > 1][:10]

    yes_words = data.get("yes_words")
    if isinstance(yes_words, list):
        identity["yes_words"] = [str(w).strip() for w in yes_words if w][:15]

    no_words = data.get("no_words")
    if isinstance(no_words, list):
        identity["no_words"] = [str(w).strip() for w in no_words if w][:15]

    if identity:
        result["brand_identity"] = identity

    return result


# ── Auto-persist ─────────────────────────────────────────────────────────────

async def auto_persist_brand_identity(
    session: AsyncSession,
    content: str,
    org_id: str,
    conversation_id: str | None = None,
) -> str | None:
    """
    Detecta si el output del agente branding contiene un Brand Book,
    lo parsea y crea un Brand en la BD.

    Returns brand_id si se creó, None si no se detectó estructura.
    """
    if not is_brand_content(content):
        return None

    parsed = parse_brand_identity(content)
    if not parsed:
        return None

    # ── Resource limit check ──
    from app.use_cases.resource_limits import check_resource_limit, ResourceLimitExceededError
    try:
        await check_resource_limit(session, org_id, "brands")
    except ResourceLimitExceededError:
        logger.warning(
            f"Brand auto-persist skipped for org {org_id}: resource limit reached"
        )
        return None

    name = parsed.get("name", "Brand — Auto-generada")
    if not parsed.get("name") and conversation_id:
        from domain.entities.conversation import Conversation
        from sqlalchemy import select
        stmt = select(Conversation.title).where(Conversation.id == conversation_id)
        result = await session.execute(stmt)
        conv_title = result.scalar_one_or_none()
        if conv_title:
            name = conv_title[:255]

    brand = Brand(
        organization_id=org_id,
        name=name,
        tagline=parsed.get("tagline"),
        status=AssetStatus.DRAFT,
        color_palette=parsed.get("color_palette"),
        typography=parsed.get("typography"),
        tones=parsed.get("tones"),
        key_messages=parsed.get("key_messages"),
        brand_identity=parsed.get("brand_identity"),
    )
    session.add(brand)
    await session.flush()

    logger.info(
        f"Auto-created brand '{name}' ({brand.id}) "
        f"json_source={'primary' if '<!--BRAND_JSON' in content else 'fallback'} "
        f"colors={bool(parsed.get('color_palette'))} "
        f"typo={bool(parsed.get('typography'))} "
        f"tones={len(parsed.get('tones', []))} "
        f"msgs={len(parsed.get('key_messages', []))} "
        f"for org {org_id}"
    )

    return brand.id
