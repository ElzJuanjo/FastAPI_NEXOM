"""
Landing Page → HTML renderer v7.
Complete rewrite fixing all extraction bugs from v6.

Fixes from v6:
  - CTA: Robust label stripping, removes all markdown residue and unmatched parens
  - Social proof: Extracts logos/media mentions, handles rating + counter properly,
    filters empty/broken items before rendering
  - Problem: Deduplicates title from body paragraphs
  - Solution: Title extraction handles partial bold ("Conoce el **Nova X Pro**")
  - Benefits: Uses section-level generic title, never picks first benefit as header
  - Transformation: Filters "Izquierda/Derecha/Visual" from titles, cleans design
    instructions from before/after text and emotional copy
  - Offer: Extracts price_new from "OFERTA HOY:" format, captures all checklist
    items (emoji-prefixed, not just ✅), correct guarantee extraction, handles
    "BONO DE ACCIÓN RÁPIDA" format
  - Testimonials: Filters design instructions from quotes, extracts all 3 testimonials,
    correct name/age/city parsing, proper avatar initials
  - FAQ: Handles numbered list format ("1. **¿Q?**\\n   A"), consolidates into
    single faq-list instead of separate section-text blocks
  - CTA Final: Deduplicates reminder vs h2, clean urgency extraction
  - General: Buttons render as <a> tags, title/footer use brand_name not raw lp.name,
    _clean_line handles "Emocional:**", "Copy:**" prefixes
"""
from __future__ import annotations
import re, html as html_mod
from typing import Optional


class LandingRenderError(Exception): ...


# ═══════════════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════════════

class Theme:
    def __init__(self, primary="#6D28D9", secondary="#1E1B4B", accent="#A78BFA",
                 background="#ffffff", text="#111827",
                 heading_font="Outfit", body_font="DM Sans"):
        self.P = primary
        self.S = secondary
        self.A = accent
        self.BG = background
        self.TX = text
        self.HF = heading_font
        self.BF = body_font

    @property
    def P_light(self):
        return _lighten(self.P, 0.2)


# ═══════════════════════════════════════════════════════════════════
# MAIN RENDERER CLASS
# ═══════════════════════════════════════════════════════════════════

class LandingHTMLRender:
    def __init__(self, lp_repo=None, brand_repo=None):
        self._lp = lp_repo
        self._br = brand_repo

    async def render(self, lp_id: str, ab_variant: str | None = None) -> str:
        lp = await self._lp.get_by_id(lp_id)
        if not lp:
            raise LandingRenderError("not found")
        brand = await self._br.get_by_id(lp.brand_id) if lp.brand_id else None
        c = brand.color_palette or {} if brand else {}
        ty = brand.typography or {} if brand else {}

        theme = Theme(
            primary=c.get("primary", "#6D28D9"),
            secondary=c.get("secondary", "#1E1B4B"),
            accent=c.get("accent", "#A78BFA"),
            background=c.get("background", "#ffffff"),
            text=c.get("text", "#111827"),
            heading_font=ty.get("heading_font", "Outfit"),
            body_font=ty.get("body_font", "DM Sans"),
        )
        brand_name = brand.name if brand else lp.name
        template_id = getattr(lp, "template", None) or "modern"
        visible = [s for s in lp.sections if s.is_visible]
        if ab_variant:
            # Include sections with no ab_group OR matching the requested variant
            visible = [s for s in visible if not getattr(s, "ab_group", None) or getattr(s, "ab_group", None) == ab_variant]
        sections = sorted(visible, key=lambda x: x.order)
        rendered = "\n".join(render_section(s, theme) for s in sections)
        campaign = getattr(lp, "campaign", "") or ""
        active_custom_css = ""
        if getattr(lp, "use_custom_css", True) and getattr(lp, "custom_css", None):
            active_custom_css = lp.custom_css
        return html_shell(
            rendered, lp.name, brand_name, theme, template_id,
            campaign=campaign,
            seo_title=getattr(lp, "seo_title", "") or "",
            seo_description=getattr(lp, "seo_description", "") or "",
            og_image=getattr(lp, "og_image", "") or "",
            analytics_config=getattr(lp, "analytics_config", None) or {},
            custom_css=active_custom_css,
        )

    async def render_one_section(self, lp_id: str, section_id: str) -> str:
        lp = await self._lp.get_by_id(lp_id)
        if not lp:
            raise LandingRenderError("not found")
        section = next((s for s in lp.sections if s.id == section_id), None)
        if not section:
            raise LandingRenderError("section not found")
        brand = await self._br.get_by_id(lp.brand_id) if lp.brand_id else None
        c = brand.color_palette or {} if brand else {}
        ty = brand.typography or {} if brand else {}
        theme = Theme(
            primary=c.get("primary", "#6D28D9"),
            secondary=c.get("secondary", "#1E1B4B"),
            accent=c.get("accent", "#A78BFA"),
            background=c.get("background", "#ffffff"),
            text=c.get("text", "#111827"),
            heading_font=ty.get("heading_font", "Outfit"),
            body_font=ty.get("body_font", "DM Sans"),
        )
        brand_name = brand.name if brand else lp.name
        template_id = getattr(lp, "template", None) or "modern"
        rendered = render_section(section, theme)
        return html_shell(rendered, lp.name, brand_name, theme, template_id)


# ═══════════════════════════════════════════════════════════════════
# TEXT CLEANING
# ═══════════════════════════════════════════════════════════════════

# All known label prefixes that should be stripped from content
_LABEL_PATTERNS = [
    # Spanish labels
    r"Titular(?:\s*\(H\d\))?", r"Headline(?:\s*\(H\d\))?",
    r"Subt[ií]tul(?:o|ar)", r"Subheadline",
    r"CTA\s*(?:Principal|Irresistible|de Acci[oó]n|Final)?",
    r"Bot[oó]n\s*(?:Principal|Irresistible|de Acci[oó]n|CTA)?",
    r"Llamado a la Acci[oó]n(?:\s*\([^)]*\))?",
    r"L[ií]nea de [Cc]onfianza(?:\s*\([^)]*\))?",
    r"Trust\s*line",
    r"T[ií]tulo", r"Texto", r"Copy(?:\s*[Ee]mocional)?",
    r"Escenario(?:\s*(?:identificable|de dolor))?",
    r"Transici[oó]n(?:\s*(?:a la? soluci[oó]n))?",
    r"Conexi[oó]n(?:\s*(?:Problema[^:]*|al? producto))?",
    r"Agitaci[oó]n(?:\s*(?:de(?:l)? dolor))?",
    r"Pain\s*agitation",
    r"Resultado", r"Emocional",
    # Pricing labels
    r"Precio\s*(?:Normal|Tachado|de Oferta|regular|HOY|en Tienda[^:]*|ancla|oferta|Outlet)?",
    r"Nuestro Precio[^:]*",
    r"Crossed-out price", r"Offer price",
    r"Opciones de pago", r"Installment(?:\s*options)?",
    r"OFERTA\s*(?:HOY)?",
    # Package / guarantee
    r"Garant[ií]a(?:\s*(?:Incondicional|Total[^:]*|de Satisfacci[oó]n[^:]*|debajo del bot[oó]n))?",
    r"Return guarantee",
    r"Contenido del [Pp]aquete", r"Package contents",
    r"Tu [Pp]aquete [Ii]ncluye", r"Incluye",
    r"Qu[eé] incluye(?:\s*tu paquete)?",
    # Urgency / CTA
    r"Urgencia(?:\s*\+\s*guarantee)?", r"Urgency(?:\s*\+\s*guarantee)?",
    r"Recordatorio(?:\s*(?:de [Bb]eneficio)?)?", r"Benefit reminder",
    r"Micro-?copy(?:\s*debajo[^:]*)?",
    r"Bot[oó]n (?:de Acci[oó]n )?[Ii]rresistible",
    # Social proof
    r"Logos(?:\s*(?:en|de)[^:]*)?",
    r"Calificaci[oó]n", r"Rating", r"Average rating",
    r"Contador", r"Customer count",
    r"Texto de clientes", r"Clientes", r"Usuarios",
    # Visual / design (should also be caught by meta filter)
    r"Imagen\s*(?:Izquierda|Derecha)(?:\s*\([^)]*\))?",
    r"(?:Sugerencia|Visual)\s*(?:sugerido|de [Ii]magen)?(?:\s*\([^)]*\))?",
    r"Suggested\s*hero\s*image(?:/video)?",
    r"Primary\s*CTA",
    # Bonus labels
    r"BONOS?\s*(?:DE ACCI[OÓ]N R[AÁ]PIDA)?(?:\s*\([^)]*\))?",
    r"Bono\s*#?\d+",
    # Transformation labels
    r"Visual\s*(?:Izquierda|Derecha)",
    r"Izquierda(?:\s*\(Antes\))?",
    r"Derecha(?:\s*\(Despu[eé]s\))?",
]

_STRIP_LABELS_RE = re.compile(
    r"^\s*\*{0,2}\s*(?:" + "|".join(_LABEL_PATTERNS) + r")\s*(?:\([^)]*\))?\s*\*{0,2}\s*:?\s*",
    re.IGNORECASE,
)

# Meta/design instruction detection
_META_KEYWORDS = [
    "diseño", "design", "formato", "visual sugerido", "objetivo", "crucial",
    "optimiz", "nota estr", "fondo", "cuadrícula", "acordeón", "carrusel",
    "tarjetas con", "imagen dividida", "split-screen", "split screen",
    "una franja", "una caja", "texto centrado", "primer impacto",
    "mobile-first", "instrucción de diseño", "sticky cta",
    "color contrastante", "sugerencia de imagen", "suggested hero",
    "formato vertical", "estilo reels", "estilo tiktok", "unboxing",
    "deslizable", "tipo chat", "tipo reseña", "foto de perfil",
    "menú desplegable", "ahorrar espacio", "detenga el scroll",
    "bordes llamativos", "color dorado", "fondo limpio",
    "como se vio en", "en gris", "looping",
]


def _is_meta_line(line: str) -> bool:
    """True if line is a design/meta instruction (drop entirely)."""
    s = line.strip()
    if not s:
        return True
    # Italic-wrapped meta: *Diseño: optimizado para...*
    if re.match(r"^\*[^*]+\*$", s) and len(s) > 10:
        inner = s.strip("* ").lower()
        if any(k in inner for k in _META_KEYWORDS):
            return True
    # Lines that START with design instruction labels
    if re.match(
        r"^\*?\s*(?:Diseño|Nota estrat[eé]gica|Visual [Ss]ugerido|"
        r"Sugerencia (?:de )?[Ii]magen|Sugerencia [Vv]isual|"
        r"Suggested hero|Formato|Instrucción de Diseño|"
        r"Video corto)\s*:",
        s, re.IGNORECASE
    ):
        return True
    # Lines that START with section type marker (### 1. HERO, etc.)
    if re.match(r"^#{1,4}\s+\d+\.\s+", s):
        return True
    # Parenthetical instructions at start
    if re.match(
        r"^\((?:Ajust|Bot[oó]n|Solo|Ejemplo|Dise[nñ]o|estilo|color|formato|looping|ej\.|Ahorras|Valorad)",
        s, re.IGNORECASE
    ):
        return True
    # Pure design instruction lines
    if re.match(
        r"^\*?\s*(?:Fondo|Cuadr[ií]cula|Acorde[oó]n|Carrusel|"
        r"Imagen dividida|Una franja|Una caja|Texto centrado|"
        r"Aseg[uú]rate de que los botones)\s*",
        s, re.IGNORECASE
    ):
        return True
    # Lines that are purely meta keywords
    low = s.lower().strip("* :")
    if low and any(low.startswith(k) for k in _META_KEYWORDS):
        if len(s) < 120:  # Short meta instruction
            return True
    return False


def _strip_markdown(text: str) -> str:
    """Remove markdown bold, italic, strikethrough, brackets."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]", r"\1", text)
    # Clean stray asterisks left behind
    text = re.sub(r"(?<!\*)\*(?!\*)", "", text)
    return text.strip()


def _clean_line(line: str) -> str:
    """Clean a single content line."""
    s = line.strip()
    s = re.sub(r"^\s*[*\-•]\s+", "", s)  # bullets
    s = re.sub(r"^\s*\d+\.\s+", "", s)  # numbered
    s = _STRIP_LABELS_RE.sub("", s)
    s = _strip_markdown(s)
    # Remove parenthetical design instructions anywhere in line
    s = re.sub(
        r"\((?:Ajust[^)]*|Bot[oó]n[^)]*|Valor[^)]*|Solo[^)]*|"
        r"Ejemplo[^)]*|Dise[nñ]o[^)]*|estilo[^)]*|color[^)]*|"
        r"formato[^)]*|looping[^)]*|ej\.[^)]*|especialmente[^)]*|"
        r"Ej\.[^)]*|Texto sobre[^)]*)\)",
        "", s, flags=re.IGNORECASE
    )
    s = s.strip(" :*")
    return s


def _clean_body(raw: str, exclude_title: str = "") -> list[str]:
    """Return list of clean, human-readable lines.

    Args:
        raw: The raw body text.
        exclude_title: If provided, skip lines that match this title
                      (to avoid duplicating the section title in body).
    """
    if not raw:
        return []
    out = []
    for line in raw.split("\n"):
        if _is_meta_line(line):
            continue
        cleaned = _clean_line(line)
        if cleaned and len(cleaned) > 3:
            # Skip if this line is basically the same as the title
            if exclude_title and _is_duplicate_of_title(cleaned, exclude_title):
                continue
            out.append(cleaned)
    return out


def _normalize_for_compare(text: str) -> str:
    """Normalize text for deduplication comparison."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _is_duplicate_of_title(line: str, title: str) -> bool:
    """Check if a body line is a duplicate (or near-duplicate) of the title."""
    if not title:
        return False
    norm_line = _normalize_for_compare(line)
    norm_title = _normalize_for_compare(title)
    if not norm_line or not norm_title:
        return False
    # Exact match
    if norm_line == norm_title:
        return True
    # One starts with the other (handles "¿Cansado..." title vs
    # "¿Cansado... o tome fotos borrosas?" in body)
    if norm_line.startswith(norm_title) or norm_title.startswith(norm_line):
        return True
    return False


def _extract_field(raw: str, *keywords: str) -> str:
    """Find first line containing any keyword, return cleaned value after it."""
    for line in raw.split("\n"):
        low = line.lower()
        for kw in keywords:
            if kw.lower() in low:
                val = re.sub(
                    r".*?" + re.escape(kw) + r"\s*:?\s*",
                    "", line, flags=re.IGNORECASE
                )
                val = _strip_markdown(val)
                val = val.strip(" *:[]()👉🚀🛒⏳⚠️")
                if len(val) > 3:
                    return val
    return ""


# ═══════════════════════════════════════════════════════════════════
# CONTENT EXTRACTORS
# ═══════════════════════════════════════════════════════════════════

def _extract_benefits(raw: str) -> list[dict]:
    """Extract ALL benefit items with any emoji prefix."""
    items = []
    # Broad emoji set that can prefix benefits
    emoji_pat = (
        r"(?:📸|🔋|🚀|💾|🛡️|💰|🔓|💳|🚚|⚡|✨|🎯|🔒|🤝|✅|🏷️|🔧|📱|🌐|💎|🎁|🔌|📦|🖥️|⌚|🎮|🎧)"
    )
    # Split on emoji + bold pattern
    parts = re.split(rf"(?={emoji_pat}\s*\*\*)", raw)
    for part in parts:
        m = re.match(
            rf"({emoji_pat})\s*\*\*([^*:]+)(?::?\s*)\*\*\s*(.*)",
            part, re.DOTALL
        )
        if m:
            icon = m.group(1)
            title = m.group(2).strip().rstrip(":")
            desc_raw = m.group(3).strip()
            desc = _strip_markdown(desc_raw)
            desc = desc.replace("\n", " ").strip()
            desc = re.sub(r"¿Qué significa para ti\?\s*", "", desc, flags=re.IGNORECASE)
            # Remove meta instructions from description
            desc = re.sub(r"\*[^*]*diseño[^*]*\*", "", desc, flags=re.IGNORECASE)
            desc = desc.strip()
            if title and len(desc) > 10:
                items.append({"icon": icon, "title": title, "description": desc[:400]})
    return items


def _extract_testimonials(raw: str) -> list[dict]:
    """Extract ALL testimonials. Handles multiple formats."""
    items = []

    # Format A: 👤 **Name, age (City)** | ⭐⭐⭐⭐⭐ "quote"
    if "👤" in raw:
        blocks = re.split(r"(?=👤)", raw)
        for block in blocks:
            if "👤" not in block:
                continue

            # Extract name — handle "Name, age (City)" or "Name (City)"
            name_m = re.search(r"\*\*([^*]+)\*\*", block)
            if not name_m:
                continue
            full_name = name_m.group(1).strip()

            # Skip if it's a design instruction
            if any(k in full_name.lower() for k in _META_KEYWORDS):
                continue

            stars = block.count("⭐") + block.count("⭐️")
            if stars == 0:
                stars = 5

            quote_m = re.search(r'["""\']([^"""\']{20,500})["""\']', block)
            if not quote_m:
                # Try without quotes — look for the text after the stars/pipe
                text_m = re.search(r'⭐️?\s*\n\s*(.{20,500}?)(?:\n\s*👤|\Z)', block, re.DOTALL)
                if text_m:
                    text = _strip_markdown(text_m.group(1).strip().strip('""\'"'))
                else:
                    continue
            else:
                text = _strip_markdown(quote_m.group(1).strip())

            # Filter out design instruction text
            if any(k in text.lower() for k in _META_KEYWORDS):
                continue

            items.append({"name": full_name, "text": text, "rating": min(stars, 5)})

    # Format B: **Testimonio N:** *Name (age)* - ⭐️⭐️⭐️ "quote"
    if not items:
        test_blocks = re.split(r"(?=\*\*Testimonio\s*\d+)", raw)
        if len(test_blocks) <= 1:
            test_blocks = re.split(r"(?=\*[^*]+\*\s*-?\s*⭐)", raw)

        for block in test_blocks:
            # For "Testimonio N:" format, skip the label and find italic name after it
            name = None
            if "**Testimonio" in block:
                # Look for *Name* after the **Testimonio N:** label
                name_m = re.search(r"\*\*Testimonio\s*\d+:?\*\*\s*\*([^*]{3,40})\*", block)
                if name_m:
                    name = name_m.group(1).strip().rstrip(" -|")
            if not name:
                # Generic italic name pattern (but NOT matching **bold** as single *)
                name_m = re.search(r"(?<!\*)\*([^*]{3,40})\*(?!\*)", block)
                if name_m:
                    name = name_m.group(1).strip().rstrip(" -|")
            if not name:
                name_m = re.search(r"\*\*([^*]{3,40})\*\*", block)
                if name_m:
                    candidate = name_m.group(1).strip().rstrip(" -|")
                    # Don't use "Testimonio N:" as name
                    if not re.match(r"Testimonio\s*\d+", candidate, re.IGNORECASE):
                        name = candidate
            if not name:
                continue

            if any(k in name.lower() for k in ["diseño", "sugerencia", "formato", "visual"]):
                continue

            stars = block.count("⭐") + block.count("⭐️")
            if stars == 0:
                stars = 5

            quote_m = re.search(r'["""\']([^"""\']{20,500})["""\']', block)
            if quote_m:
                text = _strip_markdown(quote_m.group(1).strip())
                if not any(k in text.lower() for k in _META_KEYWORDS):
                    items.append({"name": name, "text": text, "rating": min(stars, 5)})

    # Format C: Generic quote extraction as last resort
    if not items:
        for m in re.finditer(r'["""]([^"""]{20,400})["""][\s–—-]*([^\n]*)', raw):
            text = m.group(1).strip()
            author = _strip_markdown(m.group(2).strip().rstrip("⭐️. "))
            if text and not _is_meta_line(f"*{text}*") and not any(k in text.lower() for k in _META_KEYWORDS):
                items.append({"name": author or "Cliente", "text": text, "rating": 5})

    return items


def _extract_faqs(raw: str) -> list[dict]:
    """Extract ALL FAQ items. Multiple strategies."""
    items = []

    # Strategy 1: Numbered list format: "1. **¿Question?**\n   Answer"
    numbered_blocks = re.split(r"(?=\n\s*\d+\.\s+\*\*)", "\n" + raw)
    for block in numbered_blocks:
        m = re.match(r"\s*\d+\.\s+\*\*([^*]*\?[^*]*)\*\*\s*(.*)", block, re.DOTALL)
        if m:
            q = m.group(1).strip()
            a_raw = m.group(2).strip()
            a_lines = []
            for line in a_raw.split("\n"):
                s = line.strip()
                # Stop if we hit the next numbered question
                if re.match(r"\d+\.\s+\*\*", s):
                    break
                s = _strip_markdown(s)
                s = re.sub(r"^R\s*:\s*", "", s)
                s = re.sub(r"^\s*[*\-•]\s+", "", s)
                if s and len(s) > 5 and not _is_meta_line(s):
                    a_lines.append(s)
            answer = " ".join(a_lines)
            if len(q) > 5 and len(answer) > 10:
                items.append({"question": q, "answer": answer})

    if items:
        return items

    # Strategy 2: Split by **¿Question?** blocks (non-numbered)
    parts = re.split(r"(?=\*\*¿)", raw)
    for part in parts:
        m = re.match(r"\*\*([^*]*\?[^*]*)\*\*\s*(.*)", part, re.DOTALL)
        if m:
            q = m.group(1).strip()
            a_raw = m.group(2).strip()
            a_lines = []
            for line in a_raw.split("\n"):
                s = line.strip()
                if s.startswith("**¿"):
                    break
                s = _strip_markdown(s)
                s = re.sub(r"^R\s*:\s*", "", s)
                s = re.sub(r"^\s*[*\-•]\s+", "", s)
                if s and len(s) > 5 and not _is_meta_line(s):
                    a_lines.append(s)
            answer = " ".join(a_lines)
            if len(q) > 5 and len(answer) > 10:
                items.append({"question": q, "answer": answer})

    if items:
        return items

    # Strategy 3: Lines starting with ¿ followed by answer lines
    current_q = None
    current_a = []
    for line in raw.split("\n"):
        s = line.strip()
        q_m = re.match(r"\*{0,2}(¿[^?]+\?)\*{0,2}", s)
        if q_m:
            if current_q and current_a:
                items.append({
                    "question": current_q,
                    "answer": " ".join(current_a)
                })
            current_q = _strip_markdown(q_m.group(1).strip())
            current_a = []
        elif current_q and s and not s.startswith("**"):
            cleaned = _strip_markdown(s)
            cleaned = re.sub(r"^R\s*:\s*", "", cleaned)
            cleaned = re.sub(r"^\s*[*\-•]\s+", "", cleaned)
            if len(cleaned) > 5 and not _is_meta_line(cleaned):
                current_a.append(cleaned)
    if current_q and current_a:
        items.append({
            "question": current_q,
            "answer": " ".join(current_a)
        })

    return items


def _extract_offer(raw: str) -> dict:
    """Extract complete offer details."""
    offer = {}

    # Old price: ~~$599 USD~~ or "Precio en Tienda: $599" or inline "~~$599 USD~~"
    old_m = re.search(r"~~\$?\s*([\d,.]+\s*(?:USD|MXN|EUR|COP)?)\s*~~", raw)
    if old_m:
        offer["price_old"] = f"${old_m.group(1).strip()}"
    else:
        old_m = re.search(
            r"(?:Precio\s*(?:en\s*Tienda[^:]*|Normal|regular|ancla)\s*:?\s*)(?:~~)?\$?\s*([\d,.]+[^|\n~]*)",
            raw, re.IGNORECASE
        )
        if old_m:
            val = old_m.group(1).strip().rstrip("~ *")
            offer["price_old"] = f"${val}"

    # New price: Multiple formats:
    # "OFERTA HOY: $299 USD", "Precio HOY: $499", "Desde $749"
    # Also handle: **OFERTA HOY: $299 USD** (with bold)
    new_m = re.search(
        r"(?:OFERTA\s*(?:HOY)?\s*:?\s*|"
        r"Precio\s*(?:HOY|Outlet|de Oferta|especial)\s*:?\s*|"
        r"Desde\s*(?:solo\s*)?)"
        r"\$?\s*([\d,.]+\s*(?:USD|MXN|EUR|COP)?)",
        raw, re.IGNORECASE
    )
    if new_m:
        offer["price_new"] = f"${new_m.group(1).strip()}"

    # Savings: "(Ahorras $300)" or "Ahorras $300"
    savings_m = re.search(r"[Aa]horras?\s*\$?\s*([\d,.]+\s*(?:USD|MXN|EUR|COP)?)", raw)
    if savings_m:
        offer["savings"] = f"${savings_m.group(1).strip()}"

    # Installments: "12 cuotas sin intereses" or "12 meses sin intereses"
    inst_m = re.search(
        r"(?:hasta\s+)?(\d+)\s*(?:cuotas|meses)\s*(?:sin\s*intereses)?[^$\n]*(?:\$\s*([\d,.]+))?",
        raw, re.IGNORECASE
    )
    if inst_m:
        amount = f" de ${inst_m.group(2)}" if inst_m.group(2) else ""
        offer["installments"] = f"o hasta {inst_m.group(1)} cuotas sin intereses{amount}"

    # Checklist items: Lines with ✅, ✔️, or emoji-prefixed package items (📱🔌🛡️)
    checks = []
    checklist_emoji = r"(?:📱|🔌|🛡️|📦|🔧|⌚|🎮|🖥️|✅|✔️)"
    for m in re.finditer(
        rf"(?:^|\n)\s*(?:[*\-•]\s+)?{checklist_emoji}\s*([^\n]+)",
        raw
    ):
        item = _strip_markdown(m.group(1).strip())
        if len(item) > 5 and not _is_meta_line(item):
            # Exclude guarantee-like items (return/refund policies, not physical items)
            low = item.lower()
            is_guarantee = (
                any(w in low for w in ["garantía de", "guarantee", "devolución", "devolver", "reembolso"])
                and not any(w in low for w in ["funda", "protector", "mica", "cargador", "cable"])
            )
            if not is_guarantee:
                checks.append(item)
    # Fallback: "¿Qué incluye tu paquete?" section with bullet points
    if not checks:
        include_section = re.search(
            r"(?:incluye|contenido del paquete|tu paquete)\s*(?:\?|:)?\s*\*?\s*((?:\n\s*[*\-•📱🔌🛡️✅].+)+)",
            raw, re.IGNORECASE
        )
        if include_section:
            for line in include_section.group(1).split("\n"):
                item = re.sub(r"^\s*[*\-•]\s*", "", line.strip())
                item = re.sub(r"^(?:📱|🔌|🛡️|📦|✅|✔️)\s*", "", item)
                item = _strip_markdown(item)
                if len(item) > 5:
                    checks.append(item)
    offer["checklist"] = checks

    # Bonuses — multiple formats
    bonuses = []

    # Format 1 (most specific): "Bono #N: Description" lines
    for m in re.finditer(r"Bono\s*#?\d+\s*:?\s*\*{0,2}\s*([^\n]+)", raw, re.IGNORECASE):
        bonus_text = _strip_markdown(m.group(1).strip())
        if len(bonus_text) > 5:
            bonuses.append(bonus_text)

    # Format 2: "🎁 BONO DE ACCIÓN RÁPIDA:" or "🎁 GRATIS HOY:" followed by item(s)
    if not bonuses:
        bonus_section = re.search(
            r"(?:🎁\s*)?(?:BONOS?\s*(?:DE ACCI[OÓ]N R[AÁ]PIDA)?|GRATIS\s*(?:HOY)?)\s*:?\s*([^\n]+(?:\n\s*[+*\-]?\s*[^\n]+)*)",
            raw, re.IGNORECASE
        )
        if bonus_section:
            bonus_text = bonus_section.group(1)
            # Split by + or newlines with bullets
            parts = re.split(r"\s*[+]\s*|\n\s*[*\-•]\s*", bonus_text)
            for part in parts:
                b = _strip_markdown(part.strip())
                b = re.sub(r"^\s*🎁\s*", "", b)
                if len(b) > 5 and not _is_meta_line(b):
                    # Don't include guarantee lines
                    if not any(w in b.lower() for w in ["garantía", "guarantee", "🛡️"]):
                        bonuses.append(b)

    offer["bonuses"] = bonuses

    # Guarantee: Look for guarantee text, but NOT checklist items
    gu_m = re.search(
        r"(?:🛡️\s*)?(?:Garant[ií]a(?:\s*(?:de\s*)?(?:devoluci[oó]n|satisfacci[oó]n|incondicional))?[^:]*)\s*:?\s*([^\n]+)",
        raw, re.IGNORECASE
    )
    if gu_m:
        guarantee = _strip_markdown(gu_m.group(1).strip())
        # Validate it's actually about guarantee, not a checklist item
        if any(w in guarantee.lower() for w in ["día", "devol", "garant", "riesgo", "reembolso", "dinero"]):
            offer["guarantee"] = guarantee
    # Fallback: "30 días para probarlo" or "devolvemos el 100%"
    if "guarantee" not in offer:
        gu_m2 = re.search(
            r"(\d+\s*d[ií]as?\s*(?:para probarlo|de garant[ií]a|de devoluci[oó]n)[^\n]*)",
            raw, re.IGNORECASE
        )
        if gu_m2:
            offer["guarantee"] = _strip_markdown(gu_m2.group(1).strip())
    # Last resort from 🛡️ emoji line
    if "guarantee" not in offer:
        shield_m = re.search(r"🛡️\s*([^\n]+)", raw)
        if shield_m:
            text = _strip_markdown(shield_m.group(1).strip())
            if len(text) > 10:
                offer["guarantee"] = text

    return offer


def _extract_cta_text(raw: str) -> str:
    """Extract clean CTA button text."""
    for pattern in [
        # "Botón Irresistible: 👉 QUIERO MI..." or "Botón (CTA Principal): Comprar..."
        r"(?:Bot[oó]n\s*(?:\([^)]*\)\s*:?\s*)?(?:Irresistible|Principal|de Acci[oó]n|CTA)?|Primary\s*CTA)\s*:?\s*(?:\*\*)?(.+?)(?:\*\*)?$",
        r"👉\s*(.+?)$",
        r"🛒\s*(.+?)$",
    ]:
        m = re.search(pattern, raw, re.MULTILINE | re.IGNORECASE)
        if m:
            text = m.group(1).strip()
            # Remove any leading label residue
            text = re.sub(
                r"^(?:Principal|Irresistible|CTA|de Acci[oó]n)\s*(?:\([^)]*\))?\s*:?\s*\*{0,2}\s*",
                "", text, flags=re.IGNORECASE
            )
            text = _strip_markdown(text)
            text = text.strip(" *:[]()👉🚀🛒")
            # Clean unmatched parentheses
            while text.endswith(")") and text.count("(") < text.count(")"):
                text = text[:-1].rstrip()
            while text.startswith("(") and text.count("(") > text.count(")"):
                text = text[1:].lstrip()
            if len(text) > 3:
                return text
    return "Comprar ahora"


# ═══════════════════════════════════════════════════════════════════
# TITLE EXTRACTION
# ═══════════════════════════════════════════════════════════════════

_TITLE_GARBAGE = {
    "titular", "headline", "subtítulo", "visual", "imagen", "precio",
    "logos", "testimonio", "urgencia", "conexión", "h1", "h2", "agitación",
    "batería", "garantía", "pain", "social", "proof", "sugerencia",
    "sugerencia visual", "cta", "botón", "escenario", "formato",
    "título", "titulo", "texto", "copy", "resultado", "ancla",
    "price", "offer", "headline", "subheadline", "emocional",
    "izquierda", "derecha", "antes", "después",
    "oferta", "urgencia", "recordatorio", "usuarios", "calificación",
    "precios", "incluye", "paquete",
}

_TITLE_META_KEYWORDS = [
    "imagen dividida", "split-screen", "split screen",
    "optimizada para", "mobile-first", "diseño", "formato",
    "sugerencia", "visual sugerido", "instrucción",
    "deslizable", "acordeón", "carrusel", "tarjetas",
    "fondo", "cuadrícula", "color contrastante",
    "tipo chat", "tipo reseña", "foto de perfil",
    # Offer/pricing fragments that shouldn't be titles
    "cuotas sin intereses", "meses sin intereses", "llévatelo",
    "precio en tienda", "oferta hoy", "ahorras",
]


def _extract_title(section, fallback_generic: str = "") -> str:
    """Get a clean, meaningful title for the section.

    Args:
        section: The section object.
        fallback_generic: A generic title to use as last resort
                         (e.g. "Beneficios", "Tu oferta especial").
    """
    raw = section.title or ""
    cleaned = _STRIP_LABELS_RE.sub("", raw)
    cleaned = _strip_markdown(cleaned)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = cleaned.strip(": *")

    # Check if it's garbage
    is_garbage = (
        not cleaned
        or len(cleaned) < 4
        or cleaned.lower().strip(": ") in _TITLE_GARBAGE
        or cleaned.endswith(":")
        or any(k in cleaned.lower() for k in _TITLE_META_KEYWORDS)
    )

    if not is_garbage:
        return cleaned

    # Fallback chain from body
    body = section.body or ""

    # 1. Try "Titular:", "Headline:", "Título:" field
    for kw in ["titular", "headline", "título"]:
        val = _extract_field(body, kw)
        if val and len(val) > 5 and val.lower() not in _TITLE_GARBAGE:
            if not any(k in val.lower() for k in _TITLE_META_KEYWORDS):
                return val

    # 2. Try lines containing bold text — grab the FULL line
    for m in re.finditer(r"(?:^|\n)\s*(.+\*\*[^*]+\*\*.*)(?:\n|$)", body):
        candidate_raw = m.group(1).strip()
        # Strip any leading label before evaluating
        candidate_raw = _STRIP_LABELS_RE.sub("", candidate_raw).strip()
        if not candidate_raw:
            continue
        candidate = _strip_markdown(candidate_raw).strip(": *")
        # Trim at first sentence boundary for a clean title
        sentence_end = re.search(r"[.!]\s", candidate)
        if sentence_end and sentence_end.start() > 10:
            candidate = candidate[:sentence_end.start()]
        if (len(candidate) > 5
                and candidate.lower() not in _TITLE_GARBAGE
                and not any(k in candidate.lower() for k in _TITLE_META_KEYWORDS)):
            return candidate[:120]

    # 3. Pure bold blocks (fallback)
    for m in re.finditer(r"\*\*([^*:]{5,80})\*\*", body):
        candidate = m.group(1).strip()
        if (candidate.lower() not in _TITLE_GARBAGE
                and not any(k in candidate.lower() for k in _TITLE_META_KEYWORDS)):
            return candidate

    # 4. Try first clean body line (must be substantial)
    for line in _clean_body(body)[:3]:
        if 10 < len(line) < 100:
            if not any(k in line.lower() for k in _TITLE_META_KEYWORDS):
                return line[:80]

    # 5. Use the generic fallback
    return fallback_generic


# ═══════════════════════════════════════════════════════════════════
# SECTION RENDERERS
# ═══════════════════════════════════════════════════════════════════

def render_section(section, theme: Theme) -> str:
    t = section.section_type
    renderers = {
        "hero": _render_hero,
        "social_proof": _render_social_proof,
        "problem": _render_problem,
        "solution": _render_solution,
        "transformation": _render_transformation,
        "features": _render_benefits,
        "benefits": _render_benefits,
        "testimonials": _render_testimonials,
        "offer": _render_offer,
        "pricing": _render_offer,
        "faq": _render_faq,
        "cta": _render_cta,
        "product_gallery": _render_product_gallery,
        "gallery": _render_gallery_carousel,
        "specs": _render_specs,
        "video_embed": _render_video_embed,
        "comparison": _render_comparison,
        "countdown": _render_countdown,
        "trust_badges": _render_trust_badges,
        "brand_story": _render_brand_story,
        "stats_bar": _render_stats_bar,
        "logo_wall": _render_logo_wall,
        "case_study": _render_case_study,
        "urgency_banner": _render_urgency_banner,
        "process_steps": _render_process_steps,
        "lead_form": _render_lead_form,
    }
    renderer = renderers.get(t, _render_fallback)
    html = renderer(section, theme)
    # Inject id into first <section> tag for internal anchor navigation
    if not re.search(r'<section[^>]*\bid\s*=', html[:300]):
        section_id = t.replace("_", "-")
        html = html.replace('<section', f'<section id="{section_id}"', 1)
    return html


def _render_hero(section, theme: Theme) -> str:
    title = _extract_title(section)
    raw = section.body or ""
    ct = section.content or {}

    subtitle = (
        ct.get("subtitle")
        or _extract_field(raw, "subtítulo", "subtitular", "subheadline")
    )
    if not subtitle:
        lines = _clean_body(raw, exclude_title=title)
        subtitle = lines[0] if lines else ""

    trust = (
        ct.get("trust_line")
        or _extract_field(raw, "confianza", "trust line", "línea de confianza")
    )
    if trust:
        trust = _strip_markdown(trust).strip(" *")

    cta = _extract_cta_text(raw)
    cta_url = section.cta_url or ct.get("cta_url", "#")
    secondary_cta = ct.get("secondary_cta_text", "")
    secondary_cta_url = ct.get("secondary_cta_url", "#")

    hero_img = section.image_url or ct.get("image_url", "")
    img_html = ""
    if hero_img:
        img_html = f'<img src="{_e(hero_img)}" alt="{_e(title)}" class="hero-product-img" loading="lazy">'

    secondary_btn = (
        f'<a class="btn btn-secondary" href="{_e(secondary_cta_url)}">{_e(secondary_cta)}</a>'
        if secondary_cta else ""
    )

    return f"""<section class="hero">
  <div class="container">
    <h1>{_e(title)}</h1>
    <p class="subtitle">{_e(subtitle)}</p>
    <div class="hero-ctas">
      <a class="btn btn-primary" href="{_e(cta_url)}">{_e(cta)}</a>
      {secondary_btn}
    </div>
    {f'<p class="trust-line">{_e(trust)}</p>' if trust else ''}
    {img_html}
  </div>
</section>"""


def _render_social_proof(section, theme: Theme) -> str:
    ct = section.content or {}
    raw = section.body or ""
    stats = ct.get("stats", [])

    if not stats:
        # Customer count: +15,400 usuarios satisfechos
        counter_m = re.search(
            r"\+?([\d.,]+[kKmM+]*)\s+((?:clientes?|equipos?|personas?|usuarios?)[^\n.]*)",
            raw, re.IGNORECASE
        )
        if counter_m:
            stats.append({
                "value": f"+{counter_m.group(1)}",
                "label": _strip_markdown(counter_m.group(2).strip().rstrip("."))
            })

        # Rating: 4.9/5 basado en 2,300 reseñas or ⭐⭐⭐⭐⭐ 4.9/5
        rating_m = re.search(
            r"([\d.]+/\d)\s*(?:estrellas?\s*)?(?:basado\s*en\s*|en\s*)?([^\n.]*(?:reseñas?|reviews?|calificaciones?)[^\n.]*)",
            raw, re.IGNORECASE
        )
        if rating_m:
            stats.append({
                "value": rating_m.group(1),
                "label": _strip_markdown(rating_m.group(2).strip().rstrip(".")),
                "has_stars": True,
            })

        # Media logos: "Xataka, TechRadar, CNET" or "Como se vio en: ..."
        logos_m = re.search(
            r"(?:\*{0,2}\s*)?(?:Logos[^:]*:|Como se vio en[^:]*:|Medios[^:]*:)\s*\*{0,2}\s*([^\n]+)",
            raw, re.IGNORECASE
        )
        if logos_m:
            logo_text = _strip_markdown(logos_m.group(1).strip())
            # Remove parenthetical notes like (o "Como se vio en...") or (en gris)
            logo_text = re.sub(r"\([^)]*\)", "", logo_text).strip().rstrip(".")
            logo_names = [l.strip().rstrip(".") for l in re.split(r"[,;|]", logo_text) if l.strip()]
            for name in logo_names[:3]:
                if len(name) > 1 and name.lower() not in {"en gris", "o", "y", ""}:
                    stats.append({"value": name, "label": "Como se vio en"})
        else:
            # Try to find individual media mentions inline
            for media in ["Xataka", "TechRadar", "CNET", "Wired", "The Verge", "PCMag"]:
                if media.lower() in raw.lower():
                    stats.append({"value": media, "label": "Recomendado"})

    # Logos separados (desde content.logos o del parseo de medios)
    logos = ct.get("logos", [])

    # Filter out empty or broken items
    stats = [s for s in stats if s.get("value") and len(str(s.get("value", "")).strip(",. ")) > 0]

    # Separate media/logo items from real metrics
    media_labels = {"como se vio en", "recomendado", "featured in", "en medios"}
    metric_stats = [s for s in stats if s.get("label", "").lower() not in media_labels]
    logo_stats = [s for s in stats if s.get("label", "").lower() in media_labels]

    items_html = ""
    for s in metric_stats[:4]:
        stars = '<div class="proof-stars">★★★★★</div>' if s.get("has_stars") else ""
        items_html += f"""      <div class="proof-item">
        {stars}
        <div class="proof-value">{_e(str(s.get("value", "")))}</div>
        <div class="proof-label">{_e(s.get("label", ""))}</div>
      </div>\n"""

    # Logo strip — from content.logos or fallback from parsed logo_stats
    all_logos = logos or [{"name": s.get("value", "")} for s in logo_stats]
    logos_html = ""
    for lg in all_logos[:8]:
        img_url = lg.get("image_url", "")
        name = lg.get("name", "")
        if img_url:
            logos_html += f'<img src="{_e(img_url)}" alt="{_e(name)}" title="{_e(name)}">\n'
        elif name:
            logos_html += f'<span class="media-badge">{_e(name)}</span>\n'

    if not items_html and not logos_html:
        title = section.title or "Prueba Social"
        body = section.body or ""
        paras = "".join(f"<p>{_e(p.strip())}</p>" for p in body.split("\n") if p.strip())
        return f"""<section class="social-proof">
  <div class="container">
    {f'<h2>{_e(title)}</h2>' if title else ''}
    {paras}
  </div>
</section>"""

    logo_strip = (
        f'<div class="logo-wall-strip">{logos_html}</div>' if logos_html else ""
    )

    return f"""<section class="social-proof">
  <div class="container">
    {f'<div class="proof-grid">{items_html}</div>' if items_html else ''}
    {logo_strip}
  </div>
</section>"""


def _render_problem(section, theme: Theme) -> str:
    title = _extract_title(section)
    raw = section.body or ""
    lines = _clean_body(raw, exclude_title=title)
    paras = [l for l in lines if len(l.strip()) > 12]
    if not paras and not title:
        return ""
    body_html = ""
    for i, para in enumerate(paras[:7]):
        cls = ' class="pain-hook"' if i == 0 else ""
        body_html += f"      <p{cls}>{_e(para)}</p>\n"
    return f"""<section class="problem-section">
  <div class="container">
    <span class="section-label">El Problema</span>
    <h2>{_e(title) if title else "¿Te resulta familiar?"}</h2>
    <div class="problem-body">
{body_html}    </div>
  </div>
</section>"""


def _render_solution(section, theme: Theme) -> str:
    title = _extract_title(section)
    raw = section.body or ""
    lines = _clean_body(raw, exclude_title=title)
    paras = [l for l in lines if len(l.strip()) > 12]
    cta_html = ""
    if section.cta_text:
        url = section.cta_url or "#"
        cta_html = f'\n      <a href="{_e(url)}" class="btn btn-primary"><span>{_e(section.cta_text)}</span></a>'
    body_html = ""
    for i, para in enumerate(paras[:7]):
        cls = ' class="solution-lead"' if i == 0 else ""
        body_html += f"      <p{cls}>{_e(para)}</p>\n"
    return f"""<section class="solution-section">
  <div class="container">
    <div class="solution-block">
      <span class="section-label">La Solución</span>
      <h2>{_e(title) if title else "La transformación que mereces"}</h2>
      <div class="solution-body">
{body_html}      </div>{cta_html}
    </div>
  </div>
</section>"""


def _render_text_section(section, theme: Theme) -> str:
    t = section.section_type
    title = _extract_title(section)
    raw = section.body or ""
    labels = {"problem": "El problema", "solution": "La solución"}
    label = labels.get(t, "")
    bg_class = "solution-section" if t == "solution" else "section-text"

    # Exclude the title from body to prevent duplication
    lines = _clean_body(raw, exclude_title=title)

    # Find highlight candidate for problem section (the scenario/pain text)
    highlight_idx = -1
    if t == "problem":
        for i, line in enumerate(lines):
            if len(line) > 60 and any(w in line.lower() for w in [
                "eternidad", "borrosa", "congelada", "batería baja",
                "lento", "no le dura", "precios", "desanima",
                "actualizar", "quieres", "concierto", "foto",
                "sombras", "superan",
            ]):
                highlight_idx = i
                break

    body_html = ""
    for i, line in enumerate(lines):
        if len(line) > 10:
            cls = ' class="highlight-text"' if i == highlight_idx else ""
            body_html += f"      <p{cls}>{_e(line)}</p>\n"

    return f"""<section class="{bg_class}">
  <div class="container">
    <div class="text-block">
      <p class="section-label">{label}</p>
      <h2>{_e(title) or label}</h2>
{body_html}    </div>
  </div>
</section>"""


def _render_benefits(section, theme: Theme) -> str:
    # Use a generic section title, NEVER pick a benefit item as header
    title = _extract_title(section, fallback_generic="")
    raw = section.body or ""
    ct = section.content or {}

    items = ct.get("items") or _extract_benefits(raw)

    # If the extracted title matches a benefit item title, discard it
    if title and items:
        for item in items:
            if _normalize_for_compare(title) == _normalize_for_compare(item.get("title", "")):
                title = ""
                break

    label = "Beneficios" if section.section_type == "benefits" else "Características"

    # Default generic section titles
    default_titles = {
        "benefits": "¿Por qué elegir este producto?",
        "features": "Características principales",
    }
    if not title:
        title = default_titles.get(section.section_type, label)

    icons_default = ["📸", "🔋", "🚀", "💾", "🛡️", "💰", "🔓", "💳", "🚚", "⚡"]

    cards_html = ""
    for i, item in enumerate(items):
        icon = item.get("icon") or icons_default[i % len(icons_default)]
        cards_html += f"""      <div class="benefit-card">
        <div class="benefit-icon">{icon}</div>
        <h3>{_e(item.get("title", ""))}</h3>
        <p>{_e(item.get("description", ""))}</p>
      </div>\n"""

    if not items:
        lines = _clean_body(raw)
        cards_html = f'      <div class="benefit-card">{"".join(f"<p>{_e(l)}</p>" for l in lines)}</div>\n'

    return f"""<section class="benefits-section">
  <div class="container">
    <div class="benefits-header">
      <p class="section-label" style="justify-content:center">{label}</p>
      <h2>{_e(title)}</h2>
    </div>
    <div class="benefits-grid">
{cards_html}    </div>
  </div>
</section>"""


def _render_transformation(section, theme: Theme) -> str:
    title = _extract_title(section, fallback_generic="Tu vida antes y después")
    ct = section.content or {}
    raw = section.body or ""

    # Prefer structured content fields
    before_text = ct.get("before_text") or ct.get("before") or ""
    after_text = ct.get("after_text") or ct.get("after") or ""
    img_before = ct.get("image_before_url") or ct.get("before_image_url") or ""
    img_after = ct.get("image_after_url") or ct.get("after_image_url") or ""
    emotional = str(ct.get("emotional") or ct.get("copy") or "")
    before_label = str(ct.get("before_label") or "Antes")
    after_label = str(ct.get("after_label") or "Después")

    # Fall back to regex body extraction
    if not before_text or not after_text:
        before_m = re.search(
            r"(?:Izquierda|Antes|Tu celular actual)[^:]*:\s*(?:\*\s*)?([^\n]+)",
            raw, re.IGNORECASE
        )
        after_m = re.search(
            r"(?:Derecha|Despu[eé]s|Nova\s*X\s*Pro)[^:]*:\s*(?:\*\s*)?([^\n]+)",
            raw, re.IGNORECASE
        )
        if before_m and not before_text:
            bt = _strip_markdown(before_m.group(1).strip())
            bt = re.sub(r"\(Texto sobre[^)]*\)", "", bt).strip()
            bt = re.sub(r"Foto\s*(oscura|borrosa)[^.]*\+?\s*", "", bt).strip()
            before_text = bt if len(bt) >= 5 else ""
        if after_m and not after_text:
            at = _strip_markdown(after_m.group(1).strip())
            at = re.sub(r"\(Texto sobre[^)]*\)", "", at).strip()
            at = re.sub(r"Foto\s*(brillante|nítida)[^.]*\+?\s*", "", at).strip()
            after_text = at if len(at) >= 5 else ""

    if not emotional:
        emotional = _extract_field(raw, "copy emocional", "emocional", "copy")
        if not emotional:
            lines = _clean_body(raw)
            long_lines = [l for l in lines if len(l) > 40
                          and "imagen dividida" not in l.lower()
                          and "split-screen" not in l.lower()
                          and l != before_text and l != after_text]
            emotional = long_lines[-1] if long_lines else ""
    emotional = emotional.strip('""\'"')

    def _card_visual(img_url: str, emoji: str, label: str) -> str:
        if img_url:
            return f'<img src="{_e(img_url)}" alt="{_e(label)}" style="width:100%;height:180px;object-fit:cover;border-radius:12px;margin-bottom:16px">'
        return f'<div class="emoji-big">{emoji}</div>'

    return f"""<section class="transformation">
  <div class="container">
    <div class="text-block" style="text-align:center">
      <p class="section-label" style="justify-content:center">Transformación</p>
      <h2>{_e(title)}</h2>
    </div>
    <div class="transform-grid">
      <div class="transform-card before">
        {_card_visual(img_before, "😤", before_label)}
        <h4>{_e(before_label)}</h4>
        <p>{_e(before_text or "Frustración, resultados lentos, sin dirección.")}</p>
      </div>
      <div class="transform-card after">
        {_card_visual(img_after, "🤩", after_label)}
        <h4>{_e(after_label)}</h4>
        <p>{_e(after_text or "Claridad, resultados reales, confianza total.")}</p>
      </div>
    </div>
    {f'<p class="transform-text">{_e(emotional)}</p>' if emotional else ''}
  </div>
</section>"""


def _render_offer(section, theme: Theme) -> str:
    title = _extract_title(section, fallback_generic="Tu oferta especial")
    raw = section.body or ""
    ct = section.content or {}

    offer = _extract_offer(raw)

    price_old = ct.get("price_old") or offer.get("price_old", "")
    price_new = ct.get("price_new") or offer.get("price_new", "")
    guarantee = ct.get("guarantee") or offer.get("guarantee", "")
    checklist = ct.get("checklist") or offer.get("checklist", [])
    bonuses = offer.get("bonuses", [])
    installments = offer.get("installments", "")

    cta = _extract_cta_text(raw)

    # Validate title isn't a sentence fragment from offer details
    if title:
        low = title.lower()
        if any(frag in low for frag in [
            "llévatelo", "hasta", "cuotas", "meses", "precio", "oferta hoy",
            "sin intereses", "ahorras", "incluye",
        ]):
            title = "Tu oferta especial"

    checks_html = ""
    if checklist:
        items = "".join(f"<li>{_e(c)}</li>" for c in checklist)
        checks_html = f'      <ul class="offer-checklist">{items}</ul>\n'

    bonus_html = ""
    if bonuses:
        items = "".join(f"<li>{_e(b)}</li>" for b in bonuses)
        bonus_html = f"""      <div class="bonus-box">
        <div class="bonus-title">🎁 BONOS — GRATIS HOY:</div>
        <ul>{items}</ul>
      </div>\n"""

    return f"""<section class="offer-section" id="oferta">
  <div class="container">
    <div style="text-align:center;margin-bottom:48px">
      <p class="section-label" style="justify-content:center">Oferta especial</p>
      <h2 style="font-size:clamp(1.75rem,4vw,2.5rem)">{_e(title)}</h2>
    </div>
    <div class="offer-card">
      {f'<div class="price-old">{_e(price_old)}</div>' if price_old else ''}
      {f'<div class="price-new">{_e(price_new)}</div>' if price_new else ''}
      {f'<div class="price-installments">{_e(installments)}</div>' if installments else ''}
{checks_html}{bonus_html}      {f'<div class="guarantee-box"><span class="shield">🛡️</span> {_e(guarantee)}</div>' if guarantee else ''}
      <a class="btn btn-primary" style="margin-top:32px;width:100%">{_e(cta)}</a>
    </div>
  </div>
</section>"""


def _render_testimonials(section, theme: Theme) -> str:
    raw = section.body or ""
    ct = section.content or {}

    items = ct.get("testimonials") or _extract_testimonials(raw)

    cards_html = ""
    for item in items:
        name = item.get("name", "Cliente")
        text = item.get("text", "")
        rating = int(item.get("rating", 5))
        metric = item.get("metric", "")
        company = item.get("company", "")
        avatar_url = item.get("avatar_url", "")

        # Parse "Carlos M., 28 años (Ciudad de México)" into name + detail
        name_clean = re.sub(r"\([^)]*\)", "", name).strip()

        # Extract city from parentheses in original name
        city_m = re.search(r"\(([^)]+)\)", name)
        city = city_m.group(1).strip() if city_m else item.get("location", "")

        # Split name from age: "Carlos M., 28 años" → "Carlos M." + "28 años"
        name_parts = re.split(r",\s*", name_clean, maxsplit=1)
        display_name = name_parts[0].strip()
        age = name_parts[1].strip() if len(name_parts) > 1 else ""

        # Build detail line
        detail_parts = [p for p in [company or age, city] if p]
        detail = ", ".join(detail_parts)

        # Avatar: image if available, else initials
        initials = "".join(
            w[0] for w in display_name.split()[:2]
            if w and w[0].isalpha()
        ).upper() or "C"
        avatar_html = (
            f'<img src="{_e(avatar_url)}" alt="{_e(display_name)}" class="author-avatar-img">'
            if avatar_url
            else f'<div class="author-avatar">{_e(initials)}</div>'
        )

        metric_html = (
            f'<div class="testimonial-metric">{_e(metric)}</div>' if metric else ""
        )

        cards_html += f"""      <div class="testimonial-card">
        {metric_html}
        <div class="testimonial-stars">{"★" * min(rating, 5)}</div>
        <p class="testimonial-quote">&ldquo;{_e(text)}&rdquo;</p>
        <div class="testimonial-author">
          {avatar_html}
          <div class="author-info">
            <div class="name">{_e(display_name)}</div>
            {f'<div class="role">{_e(detail)}</div>' if detail else ''}
          </div>
        </div>
      </div>\n"""

    if not cards_html:
        return ""  # Don't render empty testimonials

    return f"""<section class="testimonials-section">
  <div class="container">
    <div class="testimonials-header">
      <p class="section-label" style="justify-content:center">Testimonios</p>
      <h2>Lo que dicen nuestros clientes</h2>
    </div>
    <div class="testimonials-grid">
{cards_html}    </div>
  </div>
</section>"""


def _render_faq(section, theme: Theme) -> str:
    raw = section.body or ""
    ct = section.content or {}

    items = ct.get("items") or _extract_faqs(raw)

    faqs_html = ""
    for item in items:
        faqs_html += f"""      <div class="faq-item">
        <h3>{_e(item.get("question", ""))}</h3>
        <p>{_e(item.get("answer", ""))}</p>
      </div>\n"""

    if not faqs_html:
        return ""  # Don't render empty FAQ

    return f"""<section class="faq-section">
  <div class="container">
    <div class="faq-header">
      <p class="section-label" style="justify-content:center">Preguntas frecuentes</p>
      <h2>Todo lo que necesitas saber</h2>
    </div>
    <div class="faq-list">
{faqs_html}    </div>
  </div>
</section>"""


def _render_cta(section, theme: Theme) -> str:
    raw = section.body or ""
    cta = _extract_cta_text(raw)

    # Urgency — extract once
    urgency = _extract_field(raw, "urgencia", "atención", "stock")

    # Benefit reminder — separate from urgency, and don't duplicate h2
    hardcoded_h2 = "da el salto a la tecnología que mereces"
    lines = _clean_body(raw)
    reminder_lines = [
        l for l in lines
        if len(l) > 20
        and "quiero" not in l.lower()
        and "atención" not in l.lower()
        and "stock" not in l.lower()
        and l != urgency
        and _normalize_for_compare(l) != _normalize_for_compare(hardcoded_h2)
    ]
    reminder = reminder_lines[0] if reminder_lines else ""

    return f"""<section class="cta-final" id="cta-final">
  <div class="container">
    {f'<div class="urgency-badge">⏳ {_e(urgency)}</div>' if urgency else ''}
    <h2>Da el salto a la tecnología que mereces</h2>
    {f'<p>{_e(reminder)}</p>' if reminder else ''}
    <a class="btn btn-white">{_e(cta)}</a>
  </div>
</section>"""


def _render_fallback(section, theme: Theme) -> str:
    title = _extract_title(section)
    lines = _clean_body(section.body or "", exclude_title=title)
    body = "\n".join(f"      <p>{_e(l)}</p>" for l in lines)
    return f"""<section class="section-text">
  <div class="container">
    <div class="text-block">
      <h2>{_e(title)}</h2>
{body}
    </div>
  </div>
</section>"""


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _e(t: str) -> str:
    if not t:
        return ""
    return html_mod.escape(str(t))


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    except (ValueError, IndexError):
        return f"rgba(109,40,217,{alpha})"


def _lighten(hex_color: str, amount: float = 0.2) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        return hex_color


def _render_gallery_carousel(section, theme: Theme) -> str:
    """Renderiza una galería de creativos como carrusel horizontal con controles."""
    title = _extract_title(section, fallback_generic="Galería")
    images = section.images or []
    if section.image_url and section.image_url not in images:
        images = [section.image_url] + images

    if not images:
        return f"""<section class="gallery-carousel-section">
  <div class="container">
    <h2 class="gallery-carousel-title">{_e(title)}</h2>
    <p style="text-align:center;color:var(--tx-muted);padding:60px 0">🖼 Agrega creativos a esta galería</p>
  </div>
</section>"""

    uid = f"gc{id(section)}"
    slides_html = ""
    dots_html = ""
    for i, img in enumerate(images):
        active = " active" if i == 0 else ""
        slides_html += f'<div class="gc-slide{active}" data-index="{i}"><img src="{_e(img)}" alt="Creative {i + 1}" loading="lazy"></div>\n'
        dots_html += f'<button class="gc-dot{active}" data-index="{i}" aria-label="Slide {i + 1}"></button>\n'

    return f"""<section class="gallery-carousel-section">
  <div class="container">
    <h2 class="gallery-carousel-title">{_e(title)}</h2>
    <div class="gc-wrapper" id="{uid}">
      <div class="gc-track">
        {slides_html}
      </div>
      <button class="gc-arrow gc-prev" aria-label="Previous">&#8249;</button>
      <button class="gc-arrow gc-next" aria-label="Next">&#8250;</button>
      <div class="gc-dots">
        {dots_html}
      </div>
    </div>
  </div>
  <script>
  (function(){{
    var w=document.getElementById('{uid}');if(!w)return;
    var slides=w.querySelectorAll('.gc-slide'),
        dots=w.querySelectorAll('.gc-dot'),
        cur=0,total=slides.length;
    function go(n){{
      cur=((n%total)+total)%total;
      slides.forEach(function(s,i){{s.classList.toggle('active',i===cur)}});
      dots.forEach(function(d,i){{d.classList.toggle('active',i===cur)}});
    }}
    w.querySelector('.gc-prev').onclick=function(){{go(cur-1)}};
    w.querySelector('.gc-next').onclick=function(){{go(cur+1)}};
    dots.forEach(function(d){{d.onclick=function(){{go(+d.dataset.index)}}}});
    var t=setInterval(function(){{go(cur+1)}},5000);
    w.onmouseenter=function(){{clearInterval(t)}};
    w.onmouseleave=function(){{t=setInterval(function(){{go(cur+1)}},5000)}};
  }})();
  </script>
</section>"""


def _render_product_gallery(section, theme: Theme) -> str:
    """Renderiza una galería de producto estilo e-commerce (como purocuero.shop)."""
    title = _extract_title(section, fallback_generic="")
    images = section.images or []
    ct = section.content or {}
    primary_img = section.image_url or (images[0] if images else "")
    thumb_images = images[:6] if images else []
    
    # Product details from content
    product_name = ct.get("product_name", title or "Producto")
    price = ct.get("price", "")
    price_old = ct.get("price_old", "")
    short_desc = ct.get("short_description", "")
    variants = ct.get("variants", [])  # [{label: "Color", options: ["Negro", "Café"]}]
    
    variants_html = ""
    for v in variants:
        opts = "".join(f'<button class="variant-opt">{_e(o)}</button>' for o in v.get("options", []))
        variants_html += f"""<div class="variant-group">
            <span class="variant-label">{_e(v.get("label", ""))}</span>
            <div class="variant-options">{opts}</div>
        </div>"""
    
    thumbs_html = ""
    for img in thumb_images:
        thumbs_html += f'<div class="gallery-thumb"><img src="{_e(img)}" alt="Product" loading="lazy"></div>'
    
    # If no real images, show placeholder
    if not primary_img:
        primary_img = ""
        img_tag = '<div class="gallery-placeholder">📷 Imagen del producto</div>'
    else:
        img_tag = f'<img src="{_e(primary_img)}" alt="{_e(product_name)}" class="gallery-main-img">'
    
    body_lines = _clean_body(section.body or "", exclude_title=title)
    desc_html = "".join(f"<p>{_e(l)}</p>" for l in body_lines[:3])
    
    return f"""<section class="product-gallery-section">
  <div class="container">
    <div class="product-layout">
      <div class="product-images">
        <div class="gallery-main">{img_tag}</div>
        {f'<div class="gallery-thumbs">{thumbs_html}</div>' if thumbs_html else ''}
      </div>
      <div class="product-info">
        <h1 class="product-title">{_e(product_name)}</h1>
        {f'<p class="product-short-desc">{_e(short_desc)}</p>' if short_desc else ''}
        <div class="product-pricing">
          {f'<span class="price-old">{_e(price_old)}</span>' if price_old else ''}
          {f'<span class="price-current">{_e(price)}</span>' if price else ''}
        </div>
        {variants_html}
        {desc_html}
        {f'<a class="btn btn-primary" style="width:100%;margin-top:24px">{_e(section.cta_text or "Agregar al carrito")}</a>' if section.cta_text or True else ''}
      </div>
    </div>
  </div>
</section>"""


def _render_specs(section, theme: Theme) -> str:
    """Renderiza tabla de especificaciones técnicas."""
    title = _extract_title(section, fallback_generic="Especificaciones")
    ct = section.content or {}
    specs = ct.get("specs", [])  # [{label: "Material", value: "Cuero 100%"}]
    
    if not specs:
        # Try to extract from body
        for line in (section.body or "").split("\n"):
            parts = re.split(r"[:\|–—]", line.strip(), maxsplit=1)
            if len(parts) == 2:
                label = _strip_markdown(parts[0].strip().strip("*-• "))
                value = _strip_markdown(parts[1].strip())
                if label and value and len(label) < 60:
                    specs.append({"label": label, "value": value})
    
    rows = ""
    for i, spec in enumerate(specs):
        bg = 'class="alt-row"' if i % 2 == 0 else ''
        rows += f"""<tr {bg}>
            <td class="spec-label">{_e(spec.get("label", ""))}</td>
            <td class="spec-value">{_e(spec.get("value", ""))}</td>
        </tr>"""
    
    return f"""<section class="specs-section">
  <div class="container">
    <div class="specs-header">
      <p class="section-label" style="justify-content:center">Detalles</p>
      <h2>{_e(title)}</h2>
    </div>
    <div class="specs-table-wrap">
      <table class="specs-table">
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
</section>"""


def _render_video_embed(section, theme: Theme) -> str:
    """Renderiza un embed de video (YouTube, Vimeo, o URL directa)."""
    title = _extract_title(section, fallback_generic="")
    ct = section.content or {}
    video_url = ct.get("video_url", "")
    
    # Convert YouTube URLs to embed format
    embed_url = video_url
    if "youtube.com/watch" in video_url:
        vid_id = re.search(r"v=([^&]+)", video_url)
        if vid_id:
            embed_url = f"https://www.youtube.com/embed/{vid_id.group(1)}"
    elif "youtu.be/" in video_url:
        vid_id = video_url.split("youtu.be/")[-1].split("?")[0]
        embed_url = f"https://www.youtube.com/embed/{vid_id}"
    
    caption = ct.get("caption", "")
    body_lines = _clean_body(section.body or "")
    desc = body_lines[0] if body_lines else caption
    
    return f"""<section class="video-section">
  <div class="container">
    {f'<div class="video-header"><h2>{_e(title)}</h2></div>' if title else ''}
    <div class="video-wrapper">
      <iframe src="{_e(embed_url)}" frameborder="0" allowfullscreen loading="lazy"></iframe>
    </div>
    {f'<p class="video-caption">{_e(desc)}</p>' if desc else ''}
  </div>
</section>"""


def _render_comparison(section, theme: Theme) -> str:
    """Renderiza tabla comparativa (nosotros vs competencia)."""
    title = _extract_title(section, fallback_generic="¿Por qué elegirnos?")
    ct = section.content or {}
    rows = ct.get("rows", [])  # [{feature: "Envío gratis", us: true, them: false}]
    us_label = ct.get("us_label", "Nosotros")
    them_label = ct.get("them_label", "Otros")
    
    rows_html = ""
    for row in rows:
        us_val = "✓" if row.get("us") is True else ("✗" if row.get("us") is False else _e(str(row.get("us", ""))))
        them_val = "✓" if row.get("them") is True else ("✗" if row.get("them") is False else _e(str(row.get("them", ""))))
        us_cls = "check" if row.get("us") is True else ("cross" if row.get("us") is False else "")
        them_cls = "check" if row.get("them") is True else ("cross" if row.get("them") is False else "")
        rows_html += f"""<tr>
            <td class="comp-feature">{_e(row.get("feature", ""))}</td>
            <td class="comp-val {us_cls}">{us_val}</td>
            <td class="comp-val {them_cls}">{them_val}</td>
        </tr>"""
    
    return f"""<section class="comparison-section">
  <div class="container">
    <div class="comparison-header">
      <p class="section-label" style="justify-content:center">Comparativa</p>
      <h2>{_e(title)}</h2>
    </div>
    <div class="comparison-table-wrap">
      <table class="comparison-table">
        <thead><tr>
          <th></th>
          <th class="us-col">{_e(us_label)}</th>
          <th class="them-col">{_e(them_label)}</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>
</section>"""


def _render_countdown(section, theme: Theme) -> str:
    """Renderiza un banner de countdown/urgencia."""
    title = _extract_title(section, fallback_generic="¡Oferta por tiempo limitado!")
    ct = section.content or {}
    end_date = ct.get("end_date", "")
    body_lines = _clean_body(section.body or "")
    subtitle = body_lines[0] if body_lines else ""
    cta = section.cta_text or "Aprovechar ahora"
    
    return f"""<section class="countdown-section">
  <div class="container">
    <div class="countdown-content">
      <h2>{_e(title)}</h2>
      {f'<p>{_e(subtitle)}</p>' if subtitle else ''}
      <div class="countdown-timer" data-end="{_e(end_date)}">
        <div class="timer-unit"><span class="timer-num" id="cd-days">00</span><span class="timer-label">Días</span></div>
        <div class="timer-sep">:</div>
        <div class="timer-unit"><span class="timer-num" id="cd-hours">00</span><span class="timer-label">Horas</span></div>
        <div class="timer-sep">:</div>
        <div class="timer-unit"><span class="timer-num" id="cd-mins">00</span><span class="timer-label">Min</span></div>
        <div class="timer-sep">:</div>
        <div class="timer-unit"><span class="timer-num" id="cd-secs">00</span><span class="timer-label">Seg</span></div>
      </div>
      <a class="btn btn-primary">{_e(cta)}</a>
    </div>
  </div>
</section>"""


def _render_trust_badges(section, theme: Theme) -> str:
    """Renderiza insignias de confianza (envío, garantía, pago seguro)."""
    ct = section.content or {}
    badges = ct.get("badges", [])
    
    if not badges:
        badges = [
            {"icon": "🚚", "title": "Envío gratis", "subtitle": "En pedidos +$99"},
            {"icon": "🛡️", "title": "Garantía", "subtitle": "30 días de devolución"},
            {"icon": "🔒", "title": "Pago seguro", "subtitle": "Encriptación SSL"},
            {"icon": "💬", "title": "Soporte 24/7", "subtitle": "Te ayudamos siempre"},
        ]
    
    items = ""
    for b in badges:
        items += f"""<div class="trust-badge-item">
          <span class="badge-icon">{b.get("icon", "✓")}</span>
          <div class="badge-text">
            <strong>{_e(b.get("title", ""))}</strong>
            {f'<span>{_e(b.get("subtitle", ""))}</span>' if b.get("subtitle") else ''}
          </div>
        </div>"""
    
    return f"""<section class="trust-badges-section">
  <div class="container">
    <div class="trust-badges-grid">{items}</div>
  </div>
</section>"""


def _render_brand_story(section, theme: Theme) -> str:
    title = _extract_title(section, fallback_generic="Nuestra historia")
    ct = section.content or {}
    body_lines = _clean_body(section.body or "", exclude_title=title)
    img = ct.get("image_url") or section.image_url or ""

    founder_name = ct.get("founder_name") or ""
    founder_title_str = ct.get("founder_title") or ""
    founded_year = ct.get("founded_year") or ""
    values = ct.get("values") or []

    body_html = "".join(f"  <p>{_e(l)}</p>\n" for l in body_lines)

    founder_html = ""
    if founder_name:
        founder_html = f"""<div class="founder-card" style="margin-top:32px">
      <div class="founder-initials">{_e(founder_name[:2].upper())}</div>
      <div>
        <div class="founder-name">{_e(founder_name)}</div>
        <div class="founder-title">{_e(founder_title_str or "Fundador/a")}{f" · {_e(str(founded_year))}" if founded_year else ""}</div>
      </div>
    </div>"""

    values_html = ""
    if values:
        items = "".join(f'<span style="display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:99px;border:1px solid var(--bd);font-size:.8rem;margin:4px">{_e(str(v))}</span>' for v in values[:6])
        values_html = f'<div style="margin-top:20px;display:flex;flex-wrap:wrap;gap:4px">{items}</div>'

    img_col = f"""<div class="story-image">
      <img src="{_e(img)}" alt="{_e(title)}" loading="lazy" style="width:100%;border-radius:var(--r-lg);object-fit:cover;aspect-ratio:4/3">
    </div>""" if img else ""

    return f"""<section class="brand-story-section">
  <div class="container">
    <div class="story-layout {'with-image' if img else ''}">
      <div class="story-content">
        <p class="section-label">Nuestra historia</p>
        <h2>{_e(title)}</h2>
{body_html}        {values_html}
        {founder_html}
      </div>
      {img_col}
    </div>
  </div>
</section>"""


# ═══════════════════════════════════════════════════════════════════
# NEW HIGH-IMPACT SECTION RENDERERS
# ═══════════════════════════════════════════════════════════════════

def _render_stats_bar(section, theme: Theme) -> str:
    ct = section.content or {}
    stats = ct.get("stats", [])
    if not stats:
        return ""

    items_html = ""
    for s in stats:
        icon = s.get("icon", "")
        items_html += f"""    <div class="stat-item">
      {f'<div class="stat-icon">{_e(icon)}</div>' if icon else ''}
      <div class="stat-value">{_e(str(s.get("value", "")))}</div>
      <div class="stat-label">{_e(s.get("label", ""))}</div>
    </div>\n"""

    return f"""<section class="stats-bar-section">
  <div class="container">
    <div class="stats-bar">
{items_html}    </div>
  </div>
</section>"""


def _render_logo_wall(section, theme: Theme) -> str:
    ct = section.content or {}
    logos = ct.get("logos", [])
    title = ct.get("title", "") or section.title or "Confiado por marcas líderes"

    logos_html = ""
    if not logos:
        body = section.body or ""
        paras = "".join(f"<p>{_e(p.strip())}</p>" for p in body.split("\n") if p.strip())
        return f"""<section class="logo-wall-section">
  <div class="container">
    {f'<p class="logo-wall-title">{_e(title)}</p>' if title else ''}
    {paras}
  </div>
</section>"""

    for lg in logos:
        img_url = lg.get("image_url", "")
        name = lg.get("name", "")
        if img_url:
            logos_html += f'<img src="{_e(img_url)}" alt="{_e(name)}" title="{_e(name)}">\n'
        elif name:
            logos_html += f'<span class="media-badge">{_e(name)}</span>\n'

    return f"""<section class="logo-wall-section">
  <div class="container">
    {f'<p class="logo-wall-title">{_e(title)}</p>' if title else ''}
    <div class="logo-wall-strip">
{logos_html}    </div>
  </div>
</section>"""


def _render_case_study(section, theme: Theme) -> str:
    ct = section.content or {}
    brand = ct.get("brand", "")
    founder_name = ct.get("founder_name", "")
    founder_title = ct.get("founder_title", "")
    founder_img = ct.get("founder_image_url", "")
    brand_logo = ct.get("brand_logo_url", "")
    metric_value = ct.get("metric_value", "")
    metric_label = ct.get("metric_label", "")
    metric_period = ct.get("metric_period", "")
    narrative = ct.get("narrative", "") or section.body or ""
    cta_text = ct.get("cta_text", "") or section.cta_text or ""
    cta_url = ct.get("cta_url", "") or section.cta_url or "#"

    if not metric_value:
        return ""

    founder_avatar = (
        f'<img src="{_e(founder_img)}" alt="{_e(founder_name)}" class="founder-img">'
        if founder_img
        else f'<div class="founder-initials">{"".join(w[0] for w in founder_name.split()[:2] if w).upper() or "C"}</div>'
    )

    founder_block = ""
    if founder_name:
        founder_block = f"""<div class="founder-card">
          {founder_avatar}
          <div>
            <div class="founder-name">{_e(founder_name)}</div>
            {f'<div class="founder-title">{_e(founder_title)}</div>' if founder_title else ''}
            {f'<div class="founder-title">{_e(brand)}</div>' if brand and not founder_title else ''}
          </div>
        </div>"""

    brand_logo_html = (
        f'<img src="{_e(brand_logo)}" alt="{_e(brand)}" style="height:36px;margin-bottom:24px;opacity:.8">'
        if brand_logo else ""
    )

    narrative_html = f'<p class="case-narrative">{_e(narrative[:300])}</p>' if narrative else ""
    cta_html = (
        f'<a href="{_e(cta_url)}" class="case-cta-link">{_e(cta_text)} →</a>'
        if cta_text else ""
    )

    return f"""<section class="case-study-section">
  <div class="container">
    <div class="case-study-card">
      <div class="case-proof-left">
        {brand_logo_html}
        {founder_block}
      </div>
      <div class="case-proof-right">
        <div class="case-metric-value">{_e(metric_value)}</div>
        <div class="case-metric-label">{_e(metric_label)}</div>
        {f'<div class="case-metric-period">{_e(metric_period)}</div>' if metric_period else ''}
        {narrative_html}
        {cta_html}
      </div>
    </div>
  </div>
</section>"""


def _render_urgency_banner(section, theme: Theme) -> str:
    ct = section.content or {}
    message = ct.get("message", "") or section.title or "¡Oferta por tiempo limitado!"
    cta_text = ct.get("cta_text", "") or section.cta_text or ""
    cta_url = ct.get("cta_url", "#") or section.cta_url or "#"
    end_date = ct.get("end_date", "")
    dismissible = ct.get("dismissible", True)

    cta_html = (
        f'<a href="{_e(cta_url)}" class="ub-cta">{_e(cta_text)}</a>'
        if cta_text else ""
    )
    close_btn = '<button class="ub-close" aria-label="Cerrar">×</button>' if dismissible else ""
    countdown_html = (
        f'<span class="ub-countdown" data-end="{_e(end_date)}" id="ub-cd"></span>'
        if end_date else ""
    )

    return f"""<div class="urgency-banner" role="banner">
  <span>{_e(message)}</span>
  {countdown_html}
  {cta_html}
  {close_btn}
</div>"""


def _render_process_steps(section, theme: Theme) -> str:
    ct = section.content or {}
    items = ct.get("items", [])
    title = ct.get("title", "") or _extract_title(section, fallback_generic="Cómo funciona")

    if not items:
        return ""

    steps_html = ""
    for item in items:
        step_num = item.get("step", "")
        icon = item.get("icon", "")
        step_title = item.get("title", "")
        desc = item.get("description", "")
        steps_html += f"""    <div class="step-item">
      <div class="step-circle">
        {f'<span class="step-icon">{_e(icon)}</span>' if icon else str(step_num)}
      </div>
      <h4 class="step-title">{_e(step_title)}</h4>
      {f'<p class="step-desc">{_e(desc)}</p>' if desc else ''}
    </div>\n"""

    return f"""<section class="process-steps-section">
  <div class="container">
    <div class="section-header" style="text-align:center;margin-bottom:56px">
      <h2>{_e(title)}</h2>
    </div>
    <div class="steps-flow">
{steps_html}    </div>
  </div>
</section>"""


def _render_lead_form(section, theme: Theme) -> str:
    ct = section.content or {}
    title = _extract_title(section, fallback_generic="Únete ahora")
    body = _clean_body(section.body or "")
    subtitle = body[0] if body else ct.get("subtitle", "")

    fields = ct.get("fields", [
        {"name": "name", "label": "Nombre", "type": "text", "required": True},
        {"name": "email", "label": "Email", "type": "email", "required": True},
    ])
    cta_text = section.cta_text or ct.get("cta_text", "Enviar")
    lp_id = getattr(section, "landing_page_id", "") or ct.get("lp_id", "")
    section_id = getattr(section, "id", "") or ct.get("section_id", "")

    fields_html = ""
    for f in fields:
        fname = _e(f.get("name", "field"))
        flabel = _e(f.get("label", fname))
        ftype = _e(f.get("type", "text"))
        req = "required" if f.get("required") else ""
        if ftype == "textarea":
            fields_html += f'<div class="lf-field"><label for="lf-{fname}">{flabel}</label><textarea id="lf-{fname}" name="{fname}" {req} rows="3"></textarea></div>\n'
        else:
            fields_html += f'<div class="lf-field"><label for="lf-{fname}">{flabel}</label><input id="lf-{fname}" name="{fname}" type="{ftype}" {req}></div>\n'

    api_base = ct.get("api_base", "/api/v1/landing-pages")

    return f"""<section class="lead-form-section">
  <div class="container">
    <div class="section-header" style="text-align:center;margin-bottom:40px">
      <h2>{_e(title)}</h2>
      {f'<p class="section-subtitle">{_e(subtitle)}</p>' if subtitle else ''}
    </div>
    <form class="lead-form" id="lf-{section_id or 'form'}" novalidate>
      {fields_html}
      <button type="submit" class="btn btn-primary lf-submit">{_e(cta_text)}</button>
      <p class="lf-status" style="display:none;margin-top:12px;text-align:center"></p>
    </form>
  </div>
  <script>
  (function(){{
    var form=document.getElementById('lf-{section_id or 'form'}');
    if(!form)return;
    form.addEventListener('submit',function(e){{
      e.preventDefault();
      var status=form.querySelector('.lf-status');
      var btn=form.querySelector('.lf-submit');
      btn.disabled=true;
      var data={{}};
      new FormData(form).forEach(function(v,k){{data[k]=v;}});
      fetch('{api_base}/{lp_id}/leads',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{section_id:'{section_id}',data:data}})}})
        .then(function(r){{return r.ok?r.json():Promise.reject(r);}})
        .then(function(){{
          status.style.display='block';status.style.color='var(--p)';
          status.textContent='✅ ¡Recibido! Nos ponemos en contacto pronto.';
          form.reset();
        }})
        .catch(function(){{
          status.style.display='block';status.style.color='#ef4444';
          status.textContent='Error al enviar. Intenta de nuevo.';
          btn.disabled=false;
        }});
    }});
  }})();
  </script>
</section>"""


# ═══════════════════════════════════════════════════════════════════
# HTML SHELL
# ═══════════════════════════════════════════════════════════════════

_JS_BLOCK = """<script>
(function(){
  // ── FAQ Accordion ──
  document.querySelectorAll('.faq-item h3').forEach(function(q){
    q.style.cursor='pointer';q.style.userSelect='none';
    var p=q.nextElementSibling;
    if(!p)return;
    p.style.overflow='hidden';p.style.maxHeight='0';
    p.style.transition='max-height .35s ease,opacity .3s ease,margin-top .3s ease';
    p.style.opacity='0';p.style.marginTop='0';
    var arrow=document.createElement('span');
    arrow.innerHTML='&#9658;';
    arrow.style.cssText='font-size:.7rem;transition:transform .3s;display:inline-block;margin-left:8px;opacity:.6';
    q.appendChild(arrow);
    q.addEventListener('click',function(){
      var open=q.parentElement.classList.toggle('faq-open');
      if(open){p.style.maxHeight=p.scrollHeight+'px';p.style.opacity='1';p.style.marginTop='12px';arrow.style.transform='rotate(90deg)';}
      else{p.style.maxHeight='0';p.style.opacity='0';p.style.marginTop='0';arrow.style.transform='rotate(0)';}
    });
  });

  // ── Countdown Timer ──
  document.querySelectorAll('.countdown-timer[data-end]').forEach(function(el){
    var end=new Date(el.dataset.end).getTime();
    if(isNaN(end))return;
    function pad(n){return String(n).padStart(2,'0')}
    function tick(){
      var diff=end-Date.now();
      if(diff<=0){el.innerHTML='<div style="font-size:1.2rem;font-weight:700;opacity:.7">Oferta expirada</div>';return;}
      var d=Math.floor(diff/86400000),h=Math.floor((diff%86400000)/3600000),
          m=Math.floor((diff%3600000)/60000),s=Math.floor((diff%60000)/1000);
      var days=document.getElementById('cd-days'),hours=document.getElementById('cd-hours'),
          mins=document.getElementById('cd-mins'),secs=document.getElementById('cd-secs');
      if(days)days.textContent=pad(d);if(hours)hours.textContent=pad(h);
      if(mins)mins.textContent=pad(m);if(secs)secs.textContent=pad(s);
    }
    tick();setInterval(tick,1000);
  });

  // ── Scroll class for sticky nav ──
  window.addEventListener('scroll',function(){
    document.body.classList.toggle('scrolled',window.scrollY>60);
  },{passive:true});

  // ── Urgency banner dismiss ──
  document.querySelectorAll('.urgency-banner .ub-close').forEach(function(btn){
    btn.addEventListener('click',function(){
      var banner=btn.closest('.urgency-banner');
      if(banner)banner.classList.add('dismissed');
    });
  });

  // ── Block link navigation (preview mode) ──
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[href]');
    if(a){e.preventDefault();}
  },true);

  // ── Scroll entrance animations ──
  if(window.IntersectionObserver){
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){e.target.classList.add('revealed');io.unobserve(e.target);}
      });
    },{threshold:0.07,rootMargin:'0px 0px -40px 0px'});
    document.querySelectorAll('section').forEach(function(el){
      el.classList.add('reveal');
      io.observe(el);
    });
  }

  // ── Gallery carousel ──
  document.querySelectorAll('.gc-wrapper').forEach(function(wrapper){
    var slides=wrapper.querySelectorAll('.gc-slide'),dots=wrapper.querySelectorAll('.gc-dot');
    var cur=0;
    function go(n){
      slides[cur].classList.remove('active');dots[cur]&&dots[cur].classList.remove('active');
      cur=(n+slides.length)%slides.length;
      slides[cur].classList.add('active');dots[cur]&&dots[cur].classList.add('active');
    }
    var prev=wrapper.querySelector('.gc-prev'),next=wrapper.querySelector('.gc-next');
    if(prev)prev.addEventListener('click',function(){go(cur-1);});
    if(next)next.addEventListener('click',function(){go(cur+1);});
    dots.forEach(function(d,i){d.addEventListener('click',function(){go(i);});});
  });
})();
</script>"""


def html_shell(
    body: str, name: str, brand_name: str, theme: Theme,
    template_id: str = "modern", campaign: str = "",
    seo_title: str = "", seo_description: str = "",
    og_image: str = "", analytics_config: dict = None,
    custom_css: str = "",
) -> str:
    P, S, A = theme.P, theme.S, theme.A
    BG, TX = theme.BG, theme.TX
    HF, BF = theme.HF, theme.BF
    P_light = theme.P_light

    # Clean the page title
    page_title = _strip_markdown(seo_title or name or brand_name or "Landing Page")
    low_title = page_title.lower().strip()
    if (low_title in _TITLE_GARBAGE
            or any(k in low_title for k in _TITLE_META_KEYWORDS)
            or len(page_title) < 3):
        page_title = brand_name or "Landing Page"

    # Get CSS: AI-generated custom CSS takes priority; template CSS is the fallback
    from app.use_cases.landing.templates import get_template_css, _css_base
    if custom_css:
        css = _css_base(P, S, A, BG, TX, HF, BF, P_light) + "\n" + custom_css
    else:
        css = get_template_css(template_id, P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten)

    # For elegant template, override fonts in the Google Fonts link
    if template_id == "elegant":
        HF = "Playfair Display"
        BF = "Lora"

    safe_brand = _e(brand_name)
    og_title = _e(page_title)
    og_desc = _e(seo_description or campaign or f"{brand_name} — Landing page de alta conversión")
    og_img_tag = f'<meta property="og:image" content="{_e(og_image)}">\n<meta name="twitter:image" content="{_e(og_image)}">' if og_image else ""

    # Analytics injection
    analytics_scripts = ""
    ac = analytics_config or {}
    if ac.get("gtm_id"):
        gtm = _e(ac["gtm_id"])
        analytics_scripts += f"""<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','{gtm}');</script>"""
    if ac.get("ga4_id"):
        ga4 = _e(ac["ga4_id"])
        analytics_scripts += f"""<script async src="https://www.googletagmanager.com/gtag/js?id={ga4}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{ga4}');</script>"""
    if ac.get("meta_pixel_id"):
        px = _e(ac["meta_pixel_id"])
        analytics_scripts += f"""<script>!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','{px}');fbq('track','PageView');</script>"""

    gtm_noscript = ""
    if ac.get("gtm_id"):
        gtm_noscript = f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={_e(ac["gtm_id"])}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>'

    # Lead form CSS
    lead_form_css = """
.lead-form-section { padding: 80px 0; }
.lead-form { max-width: 520px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.lf-field { display: flex; flex-direction: column; gap: 6px; }
.lf-field label { font-size: .875rem; font-weight: 600; color: var(--tx); }
.lf-field input, .lf-field textarea { padding: 12px 16px; border: 1.5px solid var(--bd); border-radius: 10px;
  font-size: 1rem; background: var(--bg); color: var(--tx); transition: border-color .2s; width: 100%; }
.lf-field input:focus, .lf-field textarea:focus { outline: none; border-color: var(--p); }
.lf-submit { width: 100%; margin-top: 8px; }
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{og_title}</title>
<meta name="description" content="{og_desc}">
<meta property="og:type" content="website">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:site_name" content="{safe_brand}">
{og_img_tag}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_desc}">
{analytics_scripts}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family={HF.replace(' ','+')}\
:wght@300;400;500;600;700;800;900&family={BF.replace(' ','+')}\
:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>
{css}
{lead_form_css}
</style>
</head>
<body>
{gtm_noscript}
<nav class="sticky-nav" aria-label="Navigation">
  <span class="nav-brand">{safe_brand}</span>
  <a href="#cta-final" class="nav-cta">Empezar ahora →</a>
</nav>
{body}
<div class="footer">&copy; 2026 {safe_brand} &middot; Powered by NEXOM</div>
{_JS_BLOCK}
</body>
</html>"""
