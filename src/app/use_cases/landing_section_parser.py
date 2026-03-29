"""
Parser de output del agente de Landing Page.
Convierte el texto markdown generado por el agente en secciones estructuradas
listas para persistir como LandingPageSection en la BD.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Mapping from agent output headers to section types
HEADER_TO_TYPE: dict[str, str] = {
    "hero": "hero",
    "above the fold": "hero",
    "encabezado": "hero",
    "social proof": "social_proof",
    "prueba social": "social_proof",
    "social proof bar": "social_proof",
    "problem": "problem",
    "problema": "problem",
    "agitation": "problem",
    "agitación": "problem",
    "solution": "solution",
    "solución": "solution",
    "benefits": "benefits",
    "beneficios": "benefits",
    "fab": "benefits",
    "features": "features",
    "características": "features",
    "transformation": "transformation",
    "transformación": "transformation",
    "before/after": "transformation",
    "antes/después": "transformation",
    "offer": "offer",
    "oferta": "offer",
    "detailed offer": "offer",
    "oferta detallada": "offer",
    "pricing": "offer",
    "precio": "offer",
    "testimonials": "testimonials",
    "testimonios": "testimonials",
    "faq": "faq",
    "preguntas frecuentes": "faq",
    "cta": "cta",
    "final cta": "cta",
    "cta final": "cta",
    "call to action": "cta",
    "llamada a la acción": "cta",
    "gallery": "gallery",
    "galería": "gallery",
}


def _normalize_header(raw: str) -> Optional[str]:
    """Map a raw header text to a LandingSectionType value."""
    cleaned = raw.lower().strip()
    # Remove leading numbers like "1." or "1)"
    cleaned = re.sub(r"^\d+[\.\)\-]\s*", "", cleaned)
    # Remove markdown bold markers
    cleaned = cleaned.replace("**", "").replace("*", "").strip()
    # Remove trailing parenthetical like "(above the fold)"
    # but also check the parenthetical itself
    paren_match = re.search(r"\(([^)]+)\)", cleaned)
    paren_content = paren_match.group(1).strip() if paren_match else ""
    cleaned_no_paren = re.sub(r"\s*\([^)]*\)", "", cleaned).strip()

    # Try exact match first
    if cleaned_no_paren in HEADER_TO_TYPE:
        return HEADER_TO_TYPE[cleaned_no_paren]

    # Try with parenthetical
    if paren_content and paren_content in HEADER_TO_TYPE:
        return HEADER_TO_TYPE[paren_content]

    # Try substring match
    for key, section_type in HEADER_TO_TYPE.items():
        if key in cleaned_no_paren or key in cleaned:
            return section_type

    return "custom"


def parse_landing_sections(content: str) -> list[dict]:
    """
    Parse the landing page agent's markdown output into structured sections.
    
    Returns a list of dicts ready for LandingPageSection creation:
    [
        {
            "section_type": "hero",
            "title": "Extracted title or headline",
            "body": "Full section content",
            "cta_text": "CTA button text if found",
            "order": 1,
            "is_visible": True,
            "content": {...}  # structured data if parseable
        },
        ...
    ]
    """
    if not content or len(content) < 50:
        return []

    sections = _split_into_sections(content)

    if len(sections) < 2:
        # Not enough structure detected — agent probably didn't follow the format
        return []

    results = []
    for order, (header, body) in enumerate(sections, start=1):
        section_type = _normalize_header(header)
        parsed = _parse_section_body(section_type, body)

        results.append({
            "section_type": section_type,
            "title": parsed.get("title", header.strip()),
            "body": parsed.get("body", body.strip()),
            "cta_text": parsed.get("cta_text"),
            "cta_url": parsed.get("cta_url"),
            "order": order,
            "is_visible": True,
            "content": parsed.get("content"),
        })

    logger.info(f"Parsed {len(results)} landing sections from agent output")
    return results


def _split_into_sections(content: str) -> list[tuple[str, str]]:
    """
    Split markdown content into (header, body) pairs.
    Detects sections by numbered headers, markdown headers, or bold headers.
    """
    # Patterns that indicate a new section:
    # 1. **HERO** (above the fold): ...
    # ## 1. HERO
    # ### HERO
    # **1. HERO**
    section_pattern = re.compile(
        r'^(?:'
        r'#{1,3}\s*\d*\.?\s*\*{0,2}([^*\n#]+)\*{0,2}'  # ### 1. **HERO**
        r'|'
        r'\d+[\.\)]\s*\*{2}([^*]+)\*{2}'                 # 1. **HERO** or 1) **HERO**
        r'|'
        r'\*{2}\d*\.?\s*([^*]+)\*{2}\s*[\(:]'            # **HERO** (above the fold):
        r'|'
        r'---+\s*\n\s*\*{2}([^*]+)\*{2}'                 # --- \n **HERO**
        r')',
        re.MULTILINE,
    )

    matches = list(section_pattern.finditer(content))

    if not matches:
        # Fallback: try splitting on lines that look like headers
        # e.g., lines that are ALL CAPS or start with a number + bold
        fallback_pattern = re.compile(
            r'^(?:\d+[\.\)]\s*\*{2}[^*]+\*{2}|#{1,3}\s+\S)',
            re.MULTILINE,
        )
        matches = list(fallback_pattern.finditer(content))

    if not matches:
        return []

    sections = []
    for i, match in enumerate(matches):
        # Extract header text from whichever group matched
        header = next((g for g in match.groups() if g), match.group(0))
        header = re.sub(r'^[\d\.\)\-\s#*]+', '', header).strip()
        header = header.rstrip(':').strip()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        if header and body:
            sections.append((header, body))

    return sections


def _parse_section_body(section_type: str, body: str) -> dict:
    """
    Extract structured data from a section body based on its type.
    Returns a dict with title, body, cta_text, and optionally content with structured data.
    """
    result: dict = {"body": body}

    # Try to extract a headline/title from the first bold line
    title_match = re.search(r'\*{2}([^*]+)\*{2}', body)
    if title_match:
        result["title"] = title_match.group(1).strip()

    # Extract CTA text
    cta_patterns = [
        r'(?:CTA|bot[oó]n|button)[\s:]*\*{0,2}["\']?([^"\'*\n]{3,50})["\']?\*{0,2}',
        r'\[([^\]]{3,40})\]\(([^)]+)\)',  # [Buy Now](url)
    ]
    for pattern in cta_patterns:
        cta_match = re.search(pattern, body, re.IGNORECASE)
        if cta_match:
            result["cta_text"] = cta_match.group(1).strip()
            if cta_match.lastindex and cta_match.lastindex >= 2:
                result["cta_url"] = cta_match.group(2).strip()
            break

    # Type-specific structured content
    content = {}

    if section_type == "hero":
        # Try to find subtitle/subheadline
        sub_match = re.search(r'(?:sub(?:head)?line|subt[ií]tulo)[\s:]*\*{0,2}([^*\n]+)\*{0,2}', body, re.IGNORECASE)
        if sub_match:
            content["subtitle"] = sub_match.group(1).strip()

        trust_match = re.search(r'(?:trust|confianza|garant[ií]a)[\s:]*([^\n]+)', body, re.IGNORECASE)
        if trust_match:
            content["trust_line"] = trust_match.group(1).strip()

    elif section_type in ("benefits", "features"):
        # Extract list items
        items = []
        item_pattern = re.compile(r'[-•✓✅⚡]\s*\*{0,2}([^*\n:]+)\*{0,2}[\s:]*([^\n]*)', re.MULTILINE)
        for m in item_pattern.finditer(body):
            items.append({
                "title": m.group(1).strip(),
                "description": m.group(2).strip() if m.group(2) else "",
            })
        if items:
            content["items"] = items

    elif section_type == "testimonials":
        # Extract testimonials
        testimonials = []
        # Try to find testimonial blocks separated by blank lines or markers
        blocks = re.split(r'\n\s*\n|\n---\n|\n\*{3}\n', body)
        for block in blocks:
            block = block.strip()
            if len(block) < 20:
                continue
            testimonial: dict = {}
            name_match = re.search(r'(?:name|nombre)[\s:]*\*{0,2}([^*\n,]+)', block, re.IGNORECASE)
            if name_match:
                testimonial["name"] = name_match.group(1).strip()

            # Try to extract quote text (usually in quotes or italic)
            quote_match = re.search(r'["\u201C]([^"\u201D]+)["\u201D]', block)
            if quote_match:
                testimonial["text"] = quote_match.group(1).strip()
            elif not name_match:
                # If no name found, the whole block might be a testimonial quote
                testimonial["text"] = block[:300]

            location_match = re.search(r'(?:city|ciudad|location|ubicaci[oó]n)[\s:]*([^,\n]+)', block, re.IGNORECASE)
            if location_match:
                testimonial["location"] = location_match.group(1).strip()

            rating_match = re.search(r'(?:rating|calificaci[oó]n|estrellas?)[\s:]*(\d)', block, re.IGNORECASE)
            if rating_match:
                testimonial["rating"] = int(rating_match.group(1))
            else:
                testimonial["rating"] = 5

            if testimonial.get("text") or testimonial.get("name"):
                testimonials.append(testimonial)

        if testimonials:
            content["testimonials"] = testimonials[:5]

    elif section_type == "faq":
        items = []
        # Pattern: **Q:** or **Pregunta:** or numbered question
        faq_pattern = re.compile(
            r'(?:\*{2}(?:Q|Pregunta|P)\d*[\s:]*\*{0,2}|(?:\d+[\.\)])\s*)([^\n?]+\??)\s*\n+(?:\*{0,2}(?:A|Respuesta|R)[\s:]*\*{0,2})?\s*([^\n*]+(?:\n(?![\d*#-])[^\n]+)*)',
            re.IGNORECASE | re.MULTILINE,
        )
        for m in faq_pattern.finditer(body):
            items.append({
                "question": m.group(1).strip().rstrip("?") + "?",
                "answer": m.group(2).strip(),
            })

        # Fallback: split by bold lines
        if not items:
            bold_lines = re.findall(r'\*{2}([^*]+)\*{2}\s*\n([^*]+?)(?=\n\*{2}|\Z)', body, re.DOTALL)
            for q, a in bold_lines:
                items.append({"question": q.strip(), "answer": a.strip()})

        if items:
            content["items"] = items

    elif section_type == "offer":
        price_old_match = re.search(r'(?:precio\s*(?:original|anterior|normal|tachado)|original\s*price|was)[\s:]*\$?([\d.,]+)', body, re.IGNORECASE)
        if price_old_match:
            content["price_old"] = "$" + price_old_match.group(1)

        price_new_match = re.search(r'(?:precio\s*(?:oferta|actual|especial|hoy)|offer\s*price|now|price)[\s:]*\$?([\d.,]+)', body, re.IGNORECASE)
        if price_new_match:
            content["price_new"] = "$" + price_new_match.group(1)

        guarantee_match = re.search(r'(?:garant[ií]a|guarantee|devoluci[oó]n|refund)[\s:]*([^\n]+)', body, re.IGNORECASE)
        if guarantee_match:
            content["guarantee"] = guarantee_match.group(1).strip()

    elif section_type == "social_proof":
        stats = []
        stat_pattern = re.compile(r'([\d.,]+[+kKmM]?)\s+([^\n,]+)', re.MULTILINE)
        for m in stat_pattern.finditer(body[:500]):
            stats.append({"value": m.group(1).strip(), "label": m.group(2).strip()})
        if stats:
            content["stats"] = stats[:6]

    if content:
        result["content"] = content

    return result


def is_landing_content(content: str) -> bool:
    """
    Heuristic to determine if an agent response contains a full landing page structure.
    Returns True if the content looks like it has multiple landing page sections.
    """
    if not content or len(content) < 200:
        return False

    # Count section header indicators
    section_indicators = 0
    indicators = [
        r'(?:^|\n)\s*\d+[\.\)]\s*\*{2}',          # 1. **HERO**
        r'(?:^|\n)\s*#{1,3}\s+\d*\.?\s*\*{0,2}\w', # ## 1. HERO
        r'\*{2}(?:HERO|hero|CTA|FAQ|BENEFITS)',     # **HERO**
        r'\*{2}(?:PROBLEMA|SOLUCIÓN|OFERTA|TESTIMONIOS|BENEFICIOS)',  # Spanish
    ]
    for pattern in indicators:
        section_indicators += len(re.findall(pattern, content, re.IGNORECASE))

    # If we detect 3+ section headers, it's likely a full landing page
    return section_indicators >= 3