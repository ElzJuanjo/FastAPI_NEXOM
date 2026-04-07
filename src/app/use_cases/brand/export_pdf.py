"""
Export Brand Guidelines como PDF profesional.
Genera un documento visual con identidad de marca completa:
paleta de colores, tipografía, tonos, mensajes clave y brand identity extendida.

Usa reportlab (Canvas + Platypus) para generación directa.
"""

from __future__ import annotations

import io
import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.pdfgen import canvas

from domain.entities.brand import Brand

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pts
MARGIN = 40
CONTENT_W = PAGE_W - 2 * MARGIN

# Grays
DARK_BG = HexColor("#0F0F14")
DARK_CARD = HexColor("#1A1A24")
DARK_BORDER = HexColor("#2A2A3A")
TEXT_PRIMARY = HexColor("#F0F0F5")
TEXT_SECONDARY = HexColor("#8888AA")
TEXT_MUTED = HexColor("#555570")
ACCENT_DEFAULT = HexColor("#7C3AED")


def _safe_hex(value: str | None, fallback: str = "#7C3AED") -> HexColor:
    """Convert a HEX string to a reportlab Color safely."""
    if not value or not isinstance(value, str):
        return HexColor(fallback)
    v = value.strip()
    if not v.startswith("#") or len(v) not in (4, 7):
        return HexColor(fallback)
    try:
        return HexColor(v)
    except Exception:
        return HexColor(fallback)


def _contrast_text(hex_str: str | None) -> Color:
    """Return white or black depending on background luminance."""
    if not hex_str or not isinstance(hex_str, str) or len(hex_str) < 7:
        return white
    try:
        r = int(hex_str[1:3], 16)
        g = int(hex_str[3:5], 16)
        b = int(hex_str[5:7], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return black if luminance > 0.5 else white
    except Exception:
        return white


def _truncate(text: str, max_len: int = 120) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# ── PDF Generator ────────────────────────────────────────────────────────────

async def export_brand_guidelines_pdf(brand: Brand) -> bytes:
    """
    Generate a professional brand guidelines PDF.

    Returns PDF as bytes ready to be sent as HTTP response.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Brand Guidelines — {brand.name}")
    c.setAuthor("NEXOM by MarkFusion")
    c.setSubject("Brand Identity Guidelines")

    palette = brand.color_palette or {}
    typo = brand.typography or {}
    tones = brand.tones or []
    messages = brand.key_messages or []
    identity = brand.brand_identity or {} if hasattr(brand, "brand_identity") else {}

    primary_hex = palette.get("primary", "#7C3AED")
    primary_color = _safe_hex(primary_hex)

    # ── Page 1: Cover ────────────────────────────────────────────────────
    _draw_cover(c, brand, primary_color, primary_hex)
    c.showPage()

    # ── Page 2: Brand Overview ───────────────────────────────────────────
    y = _draw_page_header(c, "Brand Overview", primary_color)
    y = _draw_overview_section(c, y, brand, identity)
    c.showPage()

    # ── Page 3: Color Palette ────────────────────────────────────────────
    y = _draw_page_header(c, "Color Palette", primary_color)
    y = _draw_color_palette(c, y, palette)
    c.showPage()

    # ── Page 4: Typography ───────────────────────────────────────────────
    y = _draw_page_header(c, "Typography", primary_color)
    y = _draw_typography(c, y, typo)
    c.showPage()

    # ── Page 5: Tone of Voice ────────────────────────────────────────────
    if tones or identity.get("yes_words") or identity.get("no_words"):
        y = _draw_page_header(c, "Tone of Voice", primary_color)
        y = _draw_tone_of_voice(c, y, tones, identity)
        c.showPage()

    # ── Page 6: Key Messages ─────────────────────────────────────────────
    if messages:
        y = _draw_page_header(c, "Key Messages", primary_color)
        y = _draw_key_messages(c, y, messages, primary_color)
        c.showPage()

    # ── Page 7: Brand Identity (extended) ────────────────────────────────
    if identity and any(identity.get(k) for k in ["values", "archetype", "logo_concept"]):
        y = _draw_page_header(c, "Brand Identity", primary_color)
        y = _draw_brand_identity(c, y, identity, primary_color)
        c.showPage()

    # ── Final page: footer ───────────────────────────────────────────────
    _draw_closing_page(c, brand.name, primary_color)
    c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


# ── Drawing Helpers ──────────────────────────────────────────────────────────

def _draw_cover(c: canvas.Canvas, brand: Brand, primary: HexColor, primary_hex: str):
    """Cover page with brand name, tagline, and large color block."""
    # Full-page dark background
    c.setFillColor(DARK_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Top accent bar
    c.setFillColor(primary)
    c.rect(0, PAGE_H - 8, PAGE_W, 8, fill=1, stroke=0)

    # Logo placeholder circle
    cx, cy = PAGE_W / 2, PAGE_H * 0.58
    c.setFillColor(primary)
    c.circle(cx, cy, 60, fill=1, stroke=0)

    # Initials
    initials = "".join(w[0].upper() for w in brand.name.split()[:2]) if brand.name else "B"
    c.setFillColor(_contrast_text(primary_hex))
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(cx, cy - 13, initials)

    # Brand name
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.42, brand.name or "Brand")

    # Tagline
    if brand.tagline:
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 14)
        c.drawCentredString(PAGE_W / 2, PAGE_H * 0.42 - 30, _truncate(brand.tagline, 80))

    # Subtitle
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.42 - 60, "BRAND GUIDELINES")

    # Bottom bar
    c.setFillColor(DARK_CARD)
    c.rect(0, 0, PAGE_W, 60, fill=1, stroke=0)
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, 25, "Generated by NEXOM — MarkFusion")
    c.drawRightString(PAGE_W - MARGIN, 25, "Confidential")


def _draw_page_header(c: canvas.Canvas, title: str, accent: HexColor) -> float:
    """Draw a page header and return the Y position below it."""
    # Background
    c.setFillColor(DARK_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Top accent line
    c.setFillColor(accent)
    c.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)

    # Title
    y = PAGE_H - 60
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN, y + 18, "BRAND GUIDELINES")

    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(MARGIN, y - 10, title)

    # Separator line
    y -= 25
    c.setStrokeColor(DARK_BORDER)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)

    # Page number
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_W - MARGIN, 25, f"NEXOM Brand Guidelines")

    return y - 20


def _draw_overview_section(c: canvas.Canvas, y: float, brand: Brand, identity: dict) -> float:
    """Brand overview: name, tagline, mission, vision, purpose, archetype."""
    fields = [
        ("Brand Name", brand.name),
        ("Tagline", brand.tagline),
        ("Archetype", identity.get("archetype")),
        ("Purpose", identity.get("purpose")),
        ("Mission", identity.get("mission")),
        ("Vision", identity.get("vision")),
    ]

    for label, value in fields:
        if not value:
            continue

        # Label
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, label.upper())
        y -= 18

        # Value — wrap long text
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica", 12)
        lines = _wrap_text(str(value), 70)
        for line in lines:
            c.drawString(MARGIN + 4, y, line)
            y -= 16
        y -= 14

        if y < 80:
            break

    return y


def _draw_color_palette(c: canvas.Canvas, y: float, palette: dict) -> float:
    """Draw color swatches with HEX codes and names."""
    if not palette:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 11)
        c.drawString(MARGIN, y, "No color palette defined.")
        return y - 30

    color_roles = [
        ("primary", "Primary", "Main brand color — buttons, headings, key elements"),
        ("secondary", "Secondary", "Supporting color — backgrounds, depth"),
        ("accent", "Accent", "Highlight color — CTAs, badges, links"),
        ("background", "Background", "Page backgrounds and containers"),
        ("text", "Text", "Body copy and paragraph text"),
    ]

    # Large swatches in a row
    swatch_size = 80
    gap = 16
    total_w = len([r for r in color_roles if palette.get(r[0])]) * (swatch_size + gap) - gap
    start_x = MARGIN

    for role_key, role_name, role_desc in color_roles:
        hex_val = palette.get(role_key)
        if not hex_val:
            continue

        color = _safe_hex(hex_val)

        # Swatch rectangle with rounded-ish look
        c.setFillColor(color)
        c.roundRect(start_x, y - swatch_size, swatch_size, swatch_size, 6, fill=1, stroke=0)

        # HEX label inside swatch
        txt_color = _contrast_text(hex_val)
        c.setFillColor(txt_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(start_x + swatch_size / 2, y - swatch_size + 10, hex_val.upper())

        # Role name below
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(start_x, y - swatch_size - 16, role_name)

        start_x += swatch_size + gap

    y -= swatch_size + 40

    # Detailed list below
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, y, "COLOR ROLES & USAGE")
    y -= 18

    for role_key, role_name, role_desc in color_roles:
        hex_val = palette.get(role_key)
        if not hex_val:
            continue

        # Small circle indicator
        c.setFillColor(_safe_hex(hex_val))
        c.circle(MARGIN + 6, y + 3, 5, fill=1, stroke=0)

        # Role + hex
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(MARGIN + 18, y, f"{role_name}")

        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10)
        c.drawString(MARGIN + 18 + c.stringWidth(f"{role_name}  ", "Helvetica-Bold", 10), y, f"{hex_val.upper()}")

        # Description
        y -= 15
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN + 18, y, role_desc)
        y -= 22

    return y


def _draw_typography(c: canvas.Canvas, y: float, typo: dict) -> float:
    """Draw typography section with font previews."""
    if not typo:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 11)
        c.drawString(MARGIN, y, "No typography defined.")
        return y - 30

    font_entries = [
        ("heading_font", "Headings / Display", "Used for titles, headlines, and section headers"),
        ("body_font", "Body / Paragraphs", "Used for body text, descriptions, and UI copy"),
        ("ui_font", "UI / Interface", "Used for buttons, labels, navigation, and controls"),
    ]

    for font_key, role, description in font_entries:
        font_name = typo.get(font_key)
        if not font_name:
            continue

        # Card-like background
        card_h = 110
        c.setFillColor(DARK_CARD)
        c.roundRect(MARGIN, y - card_h, CONTENT_W, card_h, 8, fill=1, stroke=0)

        # Border
        c.setStrokeColor(DARK_BORDER)
        c.setLineWidth(0.5)
        c.roundRect(MARGIN, y - card_h, CONTENT_W, card_h, 8, fill=0, stroke=1)

        inner_x = MARGIN + 20
        inner_y = y - 24

        # Role label
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(inner_x, inner_y, role.upper())
        inner_y -= 22

        # Font name (large)
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(inner_x, inner_y, font_name)
        inner_y -= 20

        # Preview text
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 11)
        c.drawString(inner_x, inner_y, "Aa Bb Cc Dd Ee Ff Gg 0123456789")
        inner_y -= 18

        # Description
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(inner_x, inner_y, description)

        y -= card_h + 16

        if y < 100:
            break

    # Typography weights info
    heading_weight = typo.get("heading_weight")
    body_weight = typo.get("body_weight")
    if heading_weight or body_weight:
        y -= 10
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN, y, "WEIGHTS")
        y -= 16
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10)
        if heading_weight:
            c.drawString(MARGIN + 4, y, f"Headings: {heading_weight}")
            y -= 16
        if body_weight:
            c.drawString(MARGIN + 4, y, f"Body: {body_weight}")
            y -= 16

    return y


def _draw_tone_of_voice(c: canvas.Canvas, y: float, tones: list, identity: dict) -> float:
    """Draw tone of voice pillars + YES/NO words."""
    if tones:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "PERSONALITY TRAITS")
        y -= 22

        # Tone chips in a row
        chip_x = MARGIN
        for tone in tones:
            text_w = c.stringWidth(tone, "Helvetica-Bold", 10) + 24
            # Chip background
            c.setFillColor(DARK_CARD)
            c.roundRect(chip_x, y - 4, text_w, 26, 13, fill=1, stroke=0)
            c.setStrokeColor(DARK_BORDER)
            c.roundRect(chip_x, y - 4, text_w, 26, 13, fill=0, stroke=1)

            c.setFillColor(TEXT_PRIMARY)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(chip_x + 12, y + 3, tone)
            chip_x += text_w + 10

            if chip_x > PAGE_W - MARGIN - 60:
                chip_x = MARGIN
                y -= 36

        y -= 40

    # YES words
    yes_words = identity.get("yes_words", [])
    if yes_words:
        c.setFillColor(HexColor("#22C55E"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "YES WORDS")
        y -= 18
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica", 10)
        words_str = ", ".join(yes_words)
        for line in _wrap_text(words_str, 80):
            c.drawString(MARGIN + 4, y, line)
            y -= 15
        y -= 12

    # NO words
    no_words = identity.get("no_words", [])
    if no_words:
        c.setFillColor(HexColor("#EF4444"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "NO WORDS")
        y -= 18
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica", 10)
        words_str = ", ".join(no_words)
        for line in _wrap_text(words_str, 80):
            c.drawString(MARGIN + 4, y, line)
            y -= 15
        y -= 12

    return y


def _draw_key_messages(c: canvas.Canvas, y: float, messages: list, accent: HexColor) -> float:
    """Draw key messages as numbered cards."""
    for i, msg in enumerate(messages, 1):
        if y < 100:
            break

        card_h = 50
        # Card bg
        c.setFillColor(DARK_CARD)
        c.roundRect(MARGIN, y - card_h, CONTENT_W, card_h, 8, fill=1, stroke=0)

        # Left accent bar
        c.setFillColor(accent)
        c.roundRect(MARGIN, y - card_h, 4, card_h, 2, fill=1, stroke=0)

        # Number
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(MARGIN + 16, y - 22, f"{i:02d}")

        # Message text
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica", 11)
        lines = _wrap_text(_truncate(msg, 100), 60)
        msg_y = y - 20
        for line in lines:
            c.drawString(MARGIN + 56, msg_y, line)
            msg_y -= 14

        y -= card_h + 12

    return y


def _draw_brand_identity(c: canvas.Canvas, y: float, identity: dict, accent: HexColor) -> float:
    """Draw extended brand identity: archetype, values, logo concept."""
    # Archetype
    archetype = identity.get("archetype")
    if archetype:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "ARCHETYPE")
        y -= 20

        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(MARGIN + 4, y, str(archetype))
        y -= 30

    # Values
    values = identity.get("values", [])
    if values:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "BRAND VALUES")
        y -= 22

        chip_x = MARGIN
        for val in values:
            text_w = c.stringWidth(val, "Helvetica", 10) + 20
            c.setFillColor(DARK_CARD)
            c.roundRect(chip_x, y - 2, text_w, 24, 12, fill=1, stroke=0)

            c.setFillColor(accent)
            c.circle(chip_x + 10, y + 8, 3, fill=1, stroke=0)

            c.setFillColor(TEXT_PRIMARY)
            c.setFont("Helvetica", 10)
            c.drawString(chip_x + 18, y + 3, val)
            chip_x += text_w + 8

            if chip_x > PAGE_W - MARGIN - 80:
                chip_x = MARGIN
                y -= 34

        y -= 40

    # Logo concept
    logo_concept = identity.get("logo_concept")
    if logo_concept:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "LOGO CONCEPT")
        y -= 18

        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10)
        for line in _wrap_text(str(logo_concept), 75):
            if y < 60:
                break
            c.drawString(MARGIN + 4, y, line)
            y -= 15
        y -= 10

    return y


def _draw_closing_page(c: canvas.Canvas, brand_name: str, accent: HexColor):
    """Final page with closing statement."""
    c.setFillColor(DARK_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Accent bar
    c.setFillColor(accent)
    c.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)

    # Center content
    cy = PAGE_H / 2

    c.setFillColor(accent)
    c.circle(PAGE_W / 2, cy + 40, 30, fill=1, stroke=0)

    initials = "".join(w[0].upper() for w in brand_name.split()[:2]) if brand_name else "B"
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(PAGE_W / 2, cy + 33, initials)

    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(PAGE_W / 2, cy - 20, f"{brand_name}")

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, cy - 44, "Brand Guidelines Document")

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    c.drawCentredString(PAGE_W / 2, cy - 80, "This document is confidential and intended for internal use only.")
    c.drawCentredString(PAGE_W / 2, cy - 95, "Generated by NEXOM — MarkFusion Agency")


def _wrap_text(text: str, max_chars: int = 70) -> list[str]:
    """Simple word-based text wrapping."""
    if not text:
        return []
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if len(test) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines