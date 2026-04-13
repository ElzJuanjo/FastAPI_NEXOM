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

    async def render(self, lp_id: str) -> str:
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
        sections = sorted(
            [s for s in lp.sections if s.is_visible], key=lambda x: x.order
        )
        rendered = "\n".join(render_section(s, theme) for s in sections)
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
        "problem": _render_text_section,
        "solution": _render_text_section,
        "transformation": _render_transformation,
        "features": _render_benefits,
        "benefits": _render_benefits,
        "testimonials": _render_testimonials,
        "offer": _render_offer,
        "pricing": _render_offer,
        "faq": _render_faq,
        "cta": _render_cta,
        "product_gallery": _render_product_gallery,
        "specs": _render_specs,
        "video_embed": _render_video_embed,
        "comparison": _render_comparison,
        "countdown": _render_countdown,
        "trust_badges": _render_trust_badges,
        "brand_story": _render_brand_story,
    }
    renderer = renderers.get(t, _render_fallback)
    return renderer(section, theme)


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
    
    hero_img = section.image_url or ct.get("image_url", "")
    img_html = ""
    if hero_img:
        img_html = f'<img src="{_e(hero_img)}" alt="{_e(title)}" class="hero-product-img" loading="lazy">'

    return f"""<section class="hero">
  <div class="container">
    <h1>{_e(title)}</h1>
    <p class="subtitle">{_e(subtitle)}</p>
    <a class="btn btn-primary">{_e(cta)}</a>
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

    # Filter out empty or broken items
    stats = [s for s in stats if s.get("value") and len(str(s["value"]).strip(",. ")) > 0]

    items_html = ""
    for s in stats[:4]:
        stars = '<div class="proof-stars">★★★★★</div>' if s.get("has_stars") else ""
        items_html += f"""      <div class="proof-item">
        {stars}
        <div class="proof-value">{_e(str(s.get("value", "")))}</div>
        <div class="proof-label">{_e(s.get("label", ""))}</div>
      </div>\n"""

    if not items_html:
        return ""  # Don't render empty social proof

    return f"""<section class="social-proof">
  <div class="container">
    <div class="proof-grid">
{items_html}    </div>
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
    raw = section.body or ""

    # Extract before/after — handle multiple line formats
    before_text = ""
    after_text = ""

    # Format: "Izquierda (Antes):" or "* **Visual Izquierda:** Foto oscura..."
    # or just "Antes:" or "Tu celular actual: ..."
    before_m = re.search(
        r"(?:Izquierda|Antes|Tu celular actual)[^:]*:\s*(?:\*\s*)?([^\n]+)",
        raw, re.IGNORECASE
    )
    after_m = re.search(
        r"(?:Derecha|Despu[eé]s|Nova\s*X\s*Pro)[^:]*:\s*(?:\*\s*)?([^\n]+)",
        raw, re.IGNORECASE
    )

    if before_m:
        before_text = _strip_markdown(before_m.group(1).strip())
        before_text = re.sub(r"\(Texto sobre[^)]*\)", "", before_text).strip()
        before_text = re.sub(r"Foto\s*(oscura|borrosa)[^.]*\+?\s*", "", before_text).strip()
        # If all visual instruction got cleaned, use a content fallback
        if len(before_text) < 5:
            before_text = ""
    if after_m:
        after_text = _strip_markdown(after_m.group(1).strip())
        after_text = re.sub(r"\(Texto sobre[^)]*\)", "", after_text).strip()
        after_text = re.sub(r"Foto\s*(brillante|nítida)[^.]*\+?\s*", "", after_text).strip()
        if len(after_text) < 5:
            after_text = ""

    # Look for "Texto:" sublines under before/after
    if not before_text:
        txt_m = re.search(
            r"(?:Izquierda|Antes)[^:]*:.*?(?:Texto\s*:?\s*\*?\s*)([^\n]+)",
            raw, re.IGNORECASE | re.DOTALL
        )
        if txt_m:
            before_text = _strip_markdown(txt_m.group(1).strip())
    if not after_text:
        txt_m = re.search(
            r"(?:Derecha|Despu[eé]s)[^:]*:.*?(?:Texto\s*:?\s*\*?\s*)([^\n]+)",
            raw, re.IGNORECASE | re.DOTALL
        )
        if txt_m:
            after_text = _strip_markdown(txt_m.group(1).strip())

    # Get emotional copy — look for "Copy Emocional:" or "Copy:" field
    emotional = _extract_field(raw, "copy emocional", "emocional")
    if not emotional:
        emotional = _extract_field(raw, "copy")
    if not emotional:
        lines = _clean_body(raw)
        long_lines = [l for l in lines if len(l) > 40
                      and "imagen dividida" not in l.lower()
                      and "split-screen" not in l.lower()
                      and "pantalla" not in l.lower()[:15]
                      and "visual" not in l.lower()[:10]
                      and l != before_text and l != after_text]
        emotional = long_lines[-1] if long_lines else ""
    # Strip surrounding quotes
    emotional = emotional.strip('""\'"')

    return f"""<section class="transformation">
  <div class="container">
    <div class="text-block" style="text-align:center">
      <p class="section-label" style="justify-content:center">Transformación</p>
      <h2>{_e(title)}</h2>
    </div>
    <div class="transform-grid">
      <div class="transform-card before">
        <div class="emoji-big">😤</div>
        <h4>Antes</h4>
        <p>{_e(before_text or 'Frustración, batería muerta, pantalla lenta.')}</p>
      </div>
      <div class="transform-card after">
        <div class="emoji-big">🤩</div>
        <h4>Después</h4>
        <p>{_e(after_text or 'Velocidad, cámara pro, batería para todo el día.')}</p>
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

        # Parse "Carlos M., 28 años (Ciudad de México)" into name + detail
        name_clean = re.sub(r"\([^)]*\)", "", name).strip()

        # Extract city from parentheses in original name
        city_m = re.search(r"\(([^)]+)\)", name)
        city = city_m.group(1).strip() if city_m else ""

        # Split name from age: "Carlos M., 28 años" → "Carlos M." + "28 años"
        name_parts = re.split(r",\s*", name_clean, maxsplit=1)
        display_name = name_parts[0].strip()
        age = name_parts[1].strip() if len(name_parts) > 1 else ""

        # Build detail line
        detail_parts = [p for p in [age, city] if p]
        detail = ", ".join(detail_parts)

        # Avatar initials — use first letter of each word in name
        initials = "".join(
            w[0] for w in display_name.split()[:2]
            if w and w[0].isalpha()
        ).upper() or "C"

        cards_html += f"""      <div class="testimonial-card">
        <div class="testimonial-stars">{"★" * min(rating, 5)}</div>
        <p class="testimonial-quote">&ldquo;{_e(text)}&rdquo;</p>
        <div class="testimonial-author">
          <div class="author-avatar">{_e(initials)}</div>
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
        <h3>{_e(item["question"])}</h3>
        <p>{_e(item["answer"])}</p>
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

    return f"""<section class="cta-final">
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
    """Renderiza sección de historia/valores de marca."""
    title = _extract_title(section, fallback_generic="Nuestra historia")
    body_lines = _clean_body(section.body or "", exclude_title=title)
    img = section.image_url or ""
    
    body_html = "".join(f"<p>{_e(l)}</p>" for l in body_lines)
    
    img_col = f"""<div class="story-image">
        <img src="{_e(img)}" alt="{_e(title)}" loading="lazy">
    </div>""" if img else ""
    
    return f"""<section class="brand-story-section">
  <div class="container">
    <div class="story-layout {'with-image' if img else ''}">
      <div class="story-content">
        <p class="section-label">Nuestra historia</p>
        <h2>{_e(title)}</h2>
        {body_html}
      </div>
      {img_col}
    </div>
  </div>
</section>"""


# ═══════════════════════════════════════════════════════════════════
# HTML SHELL
# ═══════════════════════════════════════════════════════════════════

def html_shell(body: str, name: str, brand_name: str, theme: Theme, template_id: str = "modern") -> str:
    P, S, A = theme.P, theme.S, theme.A
    BG, TX = theme.BG, theme.TX
    HF, BF = theme.HF, theme.BF
    P_light = theme.P_light

    # Clean the page title
    page_title = _strip_markdown(name or brand_name or "Landing Page")
    low_title = page_title.lower().strip()
    if (low_title in _TITLE_GARBAGE
            or any(k in low_title for k in _TITLE_META_KEYWORDS)
            or len(page_title) < 3):
        page_title = brand_name or "Landing Page"

    # Get CSS from template system
    from app.use_cases.landing.landing_templates import get_template_css
    css = get_template_css(template_id, P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten)

    # For elegant template, override fonts in the Google Fonts link
    if template_id == "elegant":
        HF = "Playfair Display"
        BF = "Lora"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_e(page_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family={HF.replace(' ','+')}\
:wght@300;400;500;600;700;800;900&family={BF.replace(' ','+')}\
:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
{body}
<div class="footer">&copy; 2026 {_e(brand_name)} &middot; Powered by NEXOM</div>
</body>
</html>"""
