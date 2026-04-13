"""
Landing Page CSS Templates — MarkFusion v2
Shopify-presentation grade. Each template has its own identity,
motion language, typographic system, and spatial rhythm.

Available templates:
  - modern    : Liquid glass morphism, editorial grid, obsidian/aurora
  - minimal   : Swiss-grid precision, ink typography, surgical spacing
  - bold      : Neo-brutalism, optical-weight contrast, kinetic feel
  - ecommerce : Conversion-engineered, warm-trust palette, CRO-first
  - dark      : Cyberpunk editorial, neon-on-void, depth layers
  - elegant   : Maison-luxury, cream serif, ceremonial whitespace
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE REGISTRY
# ═══════════════════════════════════════════════════════════════════

AVAILABLE_TEMPLATES = {
    "modern": {
        "id": "modern",
        "name": "Modern",
        "description": "Gradientes dinámicos, cards interactivas, estilo SaaS moderno",
        "preview_emoji": "🟣",
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimal",
        "description": "Espacios amplios, bordes finos, tipografía limpia, editorial",
        "preview_emoji": "⬜",
    },
    "bold": {
        "id": "bold",
        "name": "Bold",
        "description": "Tipografía grande, alto contraste, hero full-width, impactante",
        "preview_emoji": "🟥",
    },
    "ecommerce": {
        "id": "ecommerce",
        "name": "E-Commerce",
        "description": "Enfocado en producto, estilo Shopify, CTA sticky, galería",
        "preview_emoji": "🛒",
    },
    "dark": {
        "id": "dark",
        "name": "Dark",
        "description": "Fondo oscuro, acentos neón, estética tech/gaming",
        "preview_emoji": "🌑",
    },
    "elegant": {
        "id": "elegant",
        "name": "Elegant",
        "description": "Tipografía serif, paleta suave, sensación de marca de lujo",
        "preview_emoji": "✨",
    },
}


def get_template_css(template_id: str, P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten) -> str:
    getter = _TEMPLATE_MAP.get(template_id, _css_modern)
    return getter(P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten)


# ═══════════════════════════════════════════════════════════════════
# SHARED BASE CSS
# ═══════════════════════════════════════════════════════════════════

def _css_base(P, S, A, BG, TX, HF, BF, P_light):
    return f"""\
*,::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --p:{P};--p-light:{P_light};--s:{S};--a:{A};
  --bg:{BG};--tx:{TX};--tx-secondary:#64748B;--tx-muted:#94A3B8;
  --bd:#E2E8F0;--bg-alt:#FAFAF9;--bg-warm:#F5F3FF;
  --success:#10B981;--amber:#F59E0B;
  --hf:'{HF}',system-ui,sans-serif;--bf:'{BF}',system-ui,sans-serif;
  --mw:1120px;--r:16px;--r-lg:24px
}}
html{{scroll-behavior:smooth}}
body{{font-family:var(--bf);color:var(--tx);background:var(--bg);line-height:1.75;-webkit-font-smoothing:antialiased}}
h1,h2,h3,h4{{font-family:var(--hf);line-height:1.15;font-weight:700;letter-spacing:-.025em}}
.container{{max-width:var(--mw);margin:0 auto;padding:0 28px}}
.section-label{{display:inline-flex;align-items:center;gap:8px;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:var(--p);margin-bottom:16px}}
.section-label::before{{content:'';width:24px;height:2px;background:var(--a);border-radius:2px}}
.footer{{text-align:center;padding:44px 28px;font-size:.78rem;color:var(--tx-muted);border-top:1px solid var(--bd)}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(24px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero h1,.hero .subtitle,.hero .btn,.hero .trust-line{{animation:fadeUp .8s cubic-bezier(.16,1,.3,1) backwards}}
.hero .subtitle{{animation-delay:.1s}}.hero .btn{{animation-delay:.2s}}.hero .trust-line{{animation-delay:.3s}}"""


# ═══════════════════════════════════════════════════════════════════
# SHARED COMPONENT CSS
# ═══════════════════════════════════════════════════════════════════

def _css_shared_components(P, S, A, BG, TX, HF, BF, P_light, _rgba):
    p_shadow = _rgba(P, 0.3)
    return f"""\
/* ── Offer ── */
.offer-section{{padding:100px 0}}
.offer-card{{max-width:580px;margin:0 auto;padding:56px 48px;border-radius:var(--r-lg);border:2px solid var(--p);background:var(--bg);text-align:center;position:relative;overflow:hidden}}
.offer-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--p),var(--a),var(--p));background-size:200% 100%;animation:shimmer 3s ease infinite}}
@keyframes shimmer{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}
.price-old{{text-decoration:line-through;color:var(--tx-muted);font-size:1.15rem}}
.price-new{{font-family:var(--hf);font-size:3.2rem;font-weight:900;color:var(--p);margin:8px 0 4px;letter-spacing:-.04em}}
.price-installments{{font-size:.88rem;color:var(--tx-secondary);margin-bottom:32px}}
.offer-checklist{{text-align:left;margin:28px 0;list-style:none;font-size:.95rem;line-height:2.4}}
.offer-checklist li{{padding-left:32px;position:relative}}
.offer-checklist li::before{{content:'✓';position:absolute;left:0;color:var(--success);font-weight:800;font-size:1.1rem}}
.bonus-box{{margin:28px 0;padding:20px 24px;border-radius:var(--r);background:linear-gradient(135deg,#FEF3C7,rgba(253,230,138,.25));border:1px solid #FCD34D;text-align:left}}
.bonus-box .bonus-title{{font-family:var(--hf);font-weight:700;font-size:.9rem;color:#92400E;margin-bottom:8px}}
.bonus-box ul{{list-style:none;font-size:.9rem;color:#78350F;line-height:2}}
.bonus-box ul li::before{{content:'🎁 '}}
.guarantee-box{{margin-top:28px;padding:18px 24px;border-radius:var(--r);background:var(--bg-warm);font-size:.88rem;color:var(--tx-secondary);display:flex;align-items:center;gap:10px}}
.guarantee-box .shield{{font-size:1.4rem}}
/* ── FAQ ── */
.faq-section{{padding:100px 0}}
.faq-list{{max-width:720px;margin:0 auto}}
.faq-item{{border-bottom:1px solid var(--bd);padding:28px 0}}
.faq-item:last-child{{border-bottom:none}}
.faq-item h3{{font-size:1.05rem;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:12px}}
.faq-item h3::before{{content:'';width:8px;height:8px;border-radius:50%;background:var(--a);flex-shrink:0}}
.faq-item p{{color:var(--tx-secondary);font-size:.95rem;line-height:1.8;padding-left:20px}}
/* ── Transformation ── */
.transformation{{padding:100px 0;background:var(--bg-alt)}}
.transform-grid{{display:grid;grid-template-columns:1fr 1fr;gap:32px;max-width:800px;margin:40px auto 48px}}
.transform-card{{padding:40px 32px;border-radius:var(--r-lg);text-align:center}}
.transform-card.before{{background:linear-gradient(135deg,#FEE2E2,#FECACA);border:1px solid #FCA5A5}}
.transform-card.after{{background:linear-gradient(135deg,#DCFCE7,#BBF7D0);border:1px solid #86EFAC}}
.transform-card .emoji-big{{font-size:3rem;margin-bottom:16px}}
.transform-card h4{{font-size:1rem;font-weight:700;margin-bottom:12px}}
.transform-card p{{font-size:.9rem;color:var(--tx-secondary);line-height:1.7}}
.transform-text{{max-width:640px;margin:0 auto;text-align:center;font-size:1.1rem;color:var(--tx-secondary);line-height:1.85}}
/* ── Sprint 2 new sections ── */
.hero-product-img{{max-width:480px;margin:40px auto 0;border-radius:var(--r-lg);box-shadow:0 24px 64px rgba(0,0,0,.25);display:block}}
.product-gallery-section{{padding:80px 0}}
.product-layout{{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:start}}
.gallery-main{{border-radius:var(--r-lg);overflow:hidden;border:1px solid var(--bd);background:var(--bg-alt)}}
.gallery-main-img{{width:100%;height:auto;display:block;object-fit:cover;aspect-ratio:1}}
.gallery-placeholder{{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:3rem;background:var(--bg-alt);color:var(--tx-muted)}}
.gallery-thumbs{{display:flex;gap:8px;margin-top:12px}}
.gallery-thumb{{width:72px;height:72px;border-radius:12px;overflow:hidden;border:2px solid var(--bd);cursor:pointer;transition:border-color .2s}}
.gallery-thumb:hover{{border-color:var(--p)}}
.gallery-thumb img{{width:100%;height:100%;object-fit:cover}}
.product-title{{font-size:clamp(1.5rem,3vw,2rem);margin-bottom:12px}}
.product-short-desc{{color:var(--tx-secondary);margin-bottom:20px;line-height:1.75}}
.product-pricing{{display:flex;align-items:baseline;gap:12px;margin-bottom:24px}}
.price-current{{font-family:var(--hf);font-size:2rem;font-weight:800;color:var(--p)}}
.variant-group{{margin-bottom:20px}}
.variant-label{{font-size:.85rem;font-weight:600;display:block;margin-bottom:8px}}
.variant-options{{display:flex;gap:8px;flex-wrap:wrap}}
.variant-opt{{padding:8px 20px;border-radius:60px;border:1.5px solid var(--bd);background:var(--bg);font-size:.85rem;cursor:pointer;transition:all .2s}}
.variant-opt:hover,.variant-opt.active{{border-color:var(--p);color:var(--p);background:{_rgba(P,0.05)}}}
.specs-section{{padding:80px 0;background:var(--bg-alt)}}
.specs-header{{text-align:center;margin-bottom:40px}}
.specs-header h2{{font-size:clamp(1.5rem,3vw,2rem)}}
.specs-table-wrap{{max-width:680px;margin:0 auto;border-radius:var(--r);overflow:hidden;border:1px solid var(--bd)}}
.specs-table{{width:100%;border-collapse:collapse}}
.specs-table tr{{border-bottom:1px solid var(--bd)}}
.specs-table tr:last-child{{border-bottom:none}}
.specs-table td{{padding:16px 20px;font-size:.93rem}}
.spec-label{{font-weight:600;color:var(--tx);width:40%}}
.spec-value{{color:var(--tx-secondary)}}
.alt-row{{background:{_rgba(P,0.02)}}}
.video-section{{padding:80px 0}}
.video-header{{text-align:center;margin-bottom:40px}}
.video-header h2{{font-size:clamp(1.5rem,3vw,2rem)}}
.video-wrapper{{max-width:800px;margin:0 auto;border-radius:var(--r-lg);overflow:hidden;aspect-ratio:16/9;background:#000}}
.video-wrapper iframe{{width:100%;height:100%}}
.video-caption{{text-align:center;color:var(--tx-secondary);font-size:.9rem;margin-top:16px}}
.comparison-section{{padding:80px 0}}
.comparison-header{{text-align:center;margin-bottom:40px}}
.comparison-header h2{{font-size:clamp(1.5rem,3vw,2rem)}}
.comparison-table-wrap{{max-width:600px;margin:0 auto;border-radius:var(--r);overflow:hidden;border:1px solid var(--bd)}}
.comparison-table{{width:100%;border-collapse:collapse}}
.comparison-table th,.comparison-table td{{padding:14px 20px;text-align:center;border-bottom:1px solid var(--bd)}}
.comparison-table th{{font-size:.82rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700}}
.us-col{{color:var(--p);background:{_rgba(P,0.05)}}}
.them-col{{color:var(--tx-muted)}}
.comp-feature{{text-align:left;font-weight:600;font-size:.93rem}}
.comp-val.check{{color:var(--success);font-weight:700;font-size:1.2rem}}
.comp-val.cross{{color:#EF4444;font-size:1.2rem}}
.countdown-section{{padding:64px 0;background:linear-gradient(135deg,var(--s),var(--p));color:#fff;text-align:center}}
.countdown-content h2{{font-size:clamp(1.5rem,3.5vw,2.2rem);margin-bottom:12px}}
.countdown-content p{{opacity:.85;margin-bottom:32px}}
.countdown-timer{{display:flex;justify-content:center;align-items:center;gap:8px;margin-bottom:32px}}
.timer-unit{{display:flex;flex-direction:column;align-items:center}}
.timer-num{{font-family:var(--hf);font-size:2.5rem;font-weight:900;line-height:1.1;background:rgba(255,255,255,.15);border-radius:12px;padding:12px 20px;min-width:72px}}
.timer-label{{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;margin-top:6px;opacity:.7}}
.timer-sep{{font-size:2rem;font-weight:700;opacity:.5}}
.trust-badges-section{{padding:40px 0;border-top:1px solid var(--bd);border-bottom:1px solid var(--bd)}}
.trust-badges-grid{{display:flex;justify-content:center;gap:48px;flex-wrap:wrap}}
.trust-badge-item{{display:flex;align-items:center;gap:12px}}
.badge-icon{{font-size:1.5rem}}
.badge-text strong{{display:block;font-size:.88rem;font-weight:700}}
.badge-text span{{font-size:.78rem;color:var(--tx-secondary)}}
.brand-story-section{{padding:100px 0}}
.story-layout{{max-width:900px;margin:0 auto}}
.story-layout.with-image{{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:center;max-width:1100px}}
.story-content p{{color:var(--tx-secondary);line-height:1.85;margin-bottom:16px}}
.story-image img{{width:100%;border-radius:var(--r-lg);object-fit:cover}}"""


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE: MODERN
# Identity: Liquid glass morphism. Like a Vercel-meets-Linear product.
# Typography: Sharp grotesque headers, clean readable body
# Motion: Orchestrated reveals, aurora background pulse
# ═══════════════════════════════════════════════════════════════════

def _css_modern(P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten):
    p_glow   = _rgba(P, 0.35)
    p_glass  = _rgba(P, 0.08)
    p_border = _rgba(P, 0.18)
    p_hover  = _rgba(P, 0.12)
    s_glow   = _rgba(S, 0.25)
    a_glow   = _rgba(A, 0.4)

    base   = _css_base(P, S, A, BG, TX, HF, BF, P_light)
    shared = _css_shared_components(P, S, A, BG, TX, HF, BF, P_light, _rgba)

    theme = f"""
/* ── Keyframes ── */
@keyframes aurora{{
  0%,100%{{transform:translate(0,0) scale(1);opacity:.7}}
  33%{{transform:translate(40px,-30px) scale(1.08);opacity:.9}}
  66%{{transform:translate(-30px,20px) scale(.95);opacity:.6}}
}}
@keyframes floatY{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-8px)}}}}
@keyframes borderPulse{{
  0%,100%{{border-color:{p_border}}}
  50%{{border-color:{_rgba(P,0.45)}}}
}}

/* ── Buttons ── */
.btn{{
  display:inline-flex;align-items:center;justify-content:center;gap:10px;
  padding:16px 44px;font-family:var(--hf);font-weight:700;font-size:.95rem;
  border-radius:14px;border:none;cursor:pointer;letter-spacing:.01em;
  transition:all .4s cubic-bezier(.4,0,.2,1);text-decoration:none;
  position:relative;overflow:hidden;
}}
.btn::after{{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,.15) 0%,rgba(255,255,255,0) 60%);
  opacity:0;transition:opacity .3s;
}}
.btn:hover::after{{opacity:1}}
.btn-primary{{
  background:linear-gradient(135deg,var(--p) 0%,var(--s) 100%);color:#fff;
  box-shadow:0 4px 20px {p_glow},0 1px 3px rgba(0,0,0,.2),inset 0 1px 0 rgba(255,255,255,.15);
}}
.btn-primary:hover{{
  transform:translateY(-3px) scale(1.01);
  box-shadow:0 12px 40px {p_glow},0 4px 12px rgba(0,0,0,.15),inset 0 1px 0 rgba(255,255,255,.2);
}}
.btn-white{{
  background:rgba(255,255,255,.12);color:#fff;
  border:1px solid rgba(255,255,255,.25);
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 4px 16px rgba(0,0,0,.2);
}}
.btn-white:hover{{
  background:rgba(255,255,255,.2);transform:translateY(-3px);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.3),0 8px 28px rgba(0,0,0,.25);
}}

/* ── Hero ── */
.hero{{
  position:relative;padding:156px 0 128px;text-align:center;
  background:#06040F;color:#fff;overflow:hidden;
  isolation:isolate;
}}
.hero::before{{
  content:'';position:absolute;inset:-40%;
  background:
    radial-gradient(ellipse 700px 500px at 20% 40%,{_rgba(P,0.22)} 0%,transparent 65%),
    radial-gradient(ellipse 600px 600px at 80% 60%,{s_glow} 0%,transparent 65%),
    radial-gradient(ellipse 400px 400px at 50% 90%,{_rgba(A,0.12)} 0%,transparent 65%);
  animation:aurora 18s ease-in-out infinite;
  z-index:0;
}}
.hero::after{{
  content:'';position:absolute;bottom:0;left:0;right:0;height:120px;
  background:linear-gradient(to top,var(--bg) 0%,transparent 100%);z-index:1;
}}
.hero .container{{position:relative;z-index:2}}
.hero h1{{
  font-size:clamp(2.6rem,6.5vw,4.4rem);font-weight:900;line-height:1.04;
  margin-bottom:24px;letter-spacing:-.04em;
  background:linear-gradient(160deg,#fff 30%,rgba(255,255,255,.7) 60%,{A} 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}}
.hero .subtitle{{
  font-size:clamp(1rem,2.2vw,1.18rem);color:rgba(255,255,255,.65);
  max-width:540px;margin:0 auto 48px;line-height:1.8;font-weight:400;
}}
.hero .trust-line{{margin-top:48px;font-size:.82rem;color:rgba(255,255,255,.38);letter-spacing:.04em}}

/* ── Social Proof ── */
.social-proof{{
  padding:48px 0;
  background:linear-gradient(180deg,var(--bg) 0%,var(--bg-alt) 100%);
  border-bottom:1px solid var(--bd);
}}
.proof-grid{{display:flex;justify-content:center;align-items:center;gap:64px;flex-wrap:wrap}}
.proof-item{{text-align:center;padding:0 16px;position:relative}}
.proof-item+.proof-item::before{{
  content:'';position:absolute;left:0;top:50%;transform:translateY(-50%);
  height:40px;width:1px;background:var(--bd);
}}
.proof-value{{
  font-family:var(--hf);font-size:2rem;font-weight:900;color:var(--p);
  line-height:1.1;letter-spacing:-.03em;
}}
.proof-label{{font-size:.78rem;color:var(--tx-muted);margin-top:6px;letter-spacing:.04em}}
.proof-stars{{color:var(--amber);font-size:1.1rem;letter-spacing:3px;margin-bottom:4px}}

/* ── Sections ── */
.section-text{{padding:112px 0}}
.solution-section{{
  background:linear-gradient(180deg,var(--bg-alt) 0%,var(--bg-warm) 100%);
  padding:112px 0;
}}
.text-block{{max-width:680px;margin:0 auto;text-align:center}}
.text-block h2{{
  font-size:clamp(1.9rem,4vw,2.8rem);margin-bottom:28px;
  letter-spacing:-.035em;
}}
.text-block p{{font-size:1.05rem;color:var(--tx-secondary);margin-bottom:20px;line-height:1.9}}
.text-block .highlight-text{{
  color:var(--tx);font-weight:600;font-size:1.08rem;
  background:{p_glass};border:1px solid {p_border};
  border-radius:12px;padding:20px 28px;margin:36px 0;text-align:left;
  backdrop-filter:blur(8px);
}}

/* ── Benefits ── */
.benefits-section{{padding:112px 0}}
.benefits-header,.testimonials-header,.faq-header{{text-align:center;margin-bottom:64px}}
.benefits-header h2,.testimonials-header h2,.faq-header h2{{
  font-size:clamp(1.9rem,4vw,2.8rem);letter-spacing:-.035em;
}}
.benefits-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}}
.benefit-card{{
  padding:40px 36px;border-radius:20px;
  border:1px solid var(--bd);
  background:rgba(255,255,255,.6);
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  transition:all .5s cubic-bezier(.4,0,.2,1);
  position:relative;overflow:hidden;
}}
.benefit-card::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--p),var(--a),transparent);
  opacity:0;transition:opacity .4s;
}}
.benefit-card:hover{{
  border-color:{p_border};
  box-shadow:0 20px 60px {p_glass},0 4px 16px rgba(0,0,0,.04);
  transform:translateY(-6px);
}}
.benefit-card:hover::before{{opacity:1}}
.benefit-icon{{
  width:52px;height:52px;border-radius:14px;
  background:linear-gradient(135deg,{p_glass},{_rgba(A,0.08)});
  border:1px solid {p_border};
  display:flex;align-items:center;justify-content:center;
  font-size:1.4rem;margin-bottom:20px;
}}
.benefit-card h3{{font-size:1.1rem;margin-bottom:10px;font-weight:700;letter-spacing:-.02em}}
.benefit-card p{{color:var(--tx-secondary);font-size:.92rem;line-height:1.8}}

/* ── Testimonials ── */
.testimonials-section{{
  padding:112px 0;
  background:linear-gradient(180deg,var(--bg-alt) 0%,var(--bg) 100%);
}}
.testimonials-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}
.testimonial-card{{
  padding:36px 30px;border-radius:20px;
  background:rgba(255,255,255,.7);
  border:1px solid rgba(255,255,255,.8);
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  box-shadow:0 4px 24px rgba(0,0,0,.04);
  transition:all .4s;display:flex;flex-direction:column;
}}
.testimonial-card:hover{{
  box-shadow:0 16px 48px rgba(0,0,0,.08);
  transform:translateY(-4px);border-color:{p_border};
}}
.testimonial-stars{{color:var(--amber);margin-bottom:16px;font-size:1rem;letter-spacing:3px}}
.testimonial-quote{{
  font-size:.95rem;line-height:1.85;color:#374151;
  margin-bottom:24px;font-style:italic;flex:1;
}}
.testimonial-author{{display:flex;align-items:center;gap:12px}}
.author-avatar{{
  width:40px;height:40px;border-radius:50%;
  background:linear-gradient(135deg,{A},{P});
  display:flex;align-items:center;justify-content:center;
  font-family:var(--hf);font-weight:700;font-size:.82rem;color:#fff;
  box-shadow:0 4px 12px {_rgba(P,0.25)};
}}
.author-info .name{{font-weight:700;font-size:.88rem}}
.author-info .role{{font-size:.76rem;color:var(--tx-muted)}}

/* ── Final CTA ── */
.cta-final{{
  text-align:center;padding:100px 48px;
  background:#06040F;color:#fff;
  border-radius:28px;margin:64px 28px;
  position:relative;overflow:hidden;
  border:1px solid rgba(255,255,255,.08);
}}
.cta-final::before{{
  content:'';position:absolute;inset:-20%;
  background:
    radial-gradient(ellipse 500px 400px at 20% 50%,{_rgba(P,0.2)} 0%,transparent 65%),
    radial-gradient(ellipse 400px 400px at 80% 50%,{s_glow} 0%,transparent 65%);
  animation:aurora 14s ease-in-out infinite reverse;
}}
.cta-final .container{{position:relative;z-index:1}}
.cta-final .urgency-badge{{
  display:inline-flex;align-items:center;gap:8px;
  padding:8px 20px;
  background:rgba(255,255,255,.08);
  border:1px solid rgba(255,255,255,.14);
  border-radius:60px;font-size:.8rem;font-weight:600;
  margin-bottom:28px;backdrop-filter:blur(8px);
}}
.cta-final h2{{
  font-size:clamp(1.8rem,4.5vw,2.8rem);margin-bottom:20px;
  font-weight:900;letter-spacing:-.04em;
  background:linear-gradient(160deg,#fff 30%,rgba(255,255,255,.65) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}}
.cta-final p{{
  color:rgba(255,255,255,.65);margin-bottom:40px;
  font-size:1.05rem;max-width:520px;
  margin-left:auto;margin-right:auto;line-height:1.85;
}}

/* ── Responsive ── */
@media(max-width:768px){{
  .hero{{padding:100px 0 80px}}
  .benefits-grid,.testimonials-grid{{grid-template-columns:1fr}}
  .transform-grid{{grid-template-columns:1fr}}
  .proof-grid{{gap:36px}}
  .offer-card{{padding:36px 28px}}
  .cta-final{{margin:32px 16px;padding:64px 24px}}
  .section-text,.solution-section,.benefits-section,.transformation,.offer-section,.testimonials-section,.faq-section{{padding:72px 0}}
  .product-layout{{grid-template-columns:1fr}}
  .story-layout.with-image{{grid-template-columns:1fr}}
  .trust-badges-grid{{gap:24px}}
  .countdown-timer{{gap:4px}}
  .timer-num{{font-size:1.8rem;padding:8px 14px;min-width:56px}}
  .proof-item+.proof-item::before{{display:none}}
}}"""
    return base + "\n" + shared + "\n" + theme


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE: MINIMAL
# Identity: Swiss Grid Precision. Like a Bauhaus-trained designer
#           building a $50k agency site. Every pixel deliberate.
# Typography: Ultra-light display weight, surgical body
# Motion: Barely there — border reveals, opacity only
# ═══════════════════════════════════════════════════════════════════

def _css_minimal(P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten):
    base   = _css_base(P, S, A, BG, TX, HF, BF, P_light)
    shared = _css_shared_components(P, S, A, BG, TX, HF, BF, P_light, _rgba)

    theme = f"""
/* ── Buttons ── */
.btn{{
  display:inline-flex;align-items:center;justify-content:center;gap:10px;
  padding:15px 40px;font-family:var(--hf);font-weight:500;font-size:.9rem;
  border-radius:0;cursor:pointer;letter-spacing:.08em;
  text-transform:uppercase;transition:all .5s cubic-bezier(.76,0,.24,1);
  text-decoration:none;border:1.5px solid;position:relative;overflow:hidden;
}}
.btn::before{{
  content:'';position:absolute;inset:0;
  transform:translateX(-101%);transition:transform .5s cubic-bezier(.76,0,.24,1);
}}
.btn:hover::before{{transform:translateX(0)}}
.btn-primary{{
  background:var(--tx);color:var(--bg);border-color:var(--tx);
}}
.btn-primary::before{{background:var(--p)}}
.btn-primary:hover{{border-color:var(--p)}}
.btn-white{{background:transparent;color:#fff;border-color:rgba(255,255,255,.5)}}
.btn-white::before{{background:rgba(255,255,255,.12)}}
.btn-white:hover{{border-color:#fff}}
.btn span{{position:relative;z-index:1}}

/* ── Hero ── */
.hero{{
  padding:176px 0 160px;text-align:left;
  background:var(--bg);color:var(--tx);
  border-bottom:1px solid var(--bd);position:relative;
}}
.hero::after{{display:none}}
.hero .container{{position:relative;z-index:1}}
.hero h1{{
  font-size:clamp(3rem,7.5vw,5.2rem);font-weight:200;line-height:1.06;
  margin-bottom:36px;letter-spacing:-.05em;max-width:13ch;
}}
.hero h1 strong{{font-weight:700;color:var(--p)}}
.hero .subtitle{{
  font-size:1.1rem;color:var(--tx-muted);
  max-width:44ch;margin:0 0 52px;line-height:2;font-weight:400;
}}
.hero .trust-line{{
  margin-top:60px;font-size:.73rem;color:var(--tx-muted);
  letter-spacing:.16em;text-transform:uppercase;
}}

/* ── Social Proof ── */
.social-proof{{padding:56px 0;border-bottom:1px solid var(--bd)}}
.proof-grid{{display:flex;justify-content:flex-start;align-items:center;gap:0;flex-wrap:wrap}}
.proof-item{{
  text-align:left;padding:0 48px 0 0;margin:0 48px 0 0;
  border-right:1px solid var(--bd);
}}
.proof-item:last-child{{border-right:none;padding-right:0;margin-right:0}}
.proof-value{{
  font-family:var(--hf);font-size:1.6rem;font-weight:200;
  color:var(--tx);line-height:1.1;letter-spacing:-.04em;
}}
.proof-label{{
  font-size:.7rem;color:var(--tx-muted);margin-top:6px;
  text-transform:uppercase;letter-spacing:.14em;
}}
.proof-stars{{color:var(--tx);font-size:.9rem;letter-spacing:3px;margin-bottom:4px}}

/* ── Sections ── */
.section-text{{padding:120px 0}}
.solution-section{{padding:120px 0;border-top:1px solid var(--bd)}}
.text-block{{max-width:600px;margin:0}}
.text-block h2{{
  font-size:clamp(1.7rem,4vw,2.4rem);margin-bottom:28px;
  font-weight:200;letter-spacing:-.04em;
}}
.text-block p{{font-size:1rem;color:var(--tx-secondary);margin-bottom:20px;line-height:2.1}}
.text-block .highlight-text{{
  color:var(--tx);font-weight:400;font-size:1.06rem;
  border-left:1px solid var(--p);padding:4px 0 4px 28px;
  margin:40px 0;font-style:italic;
}}

/* ── Benefits ── */
.benefits-section{{padding:120px 0;border-top:1px solid var(--bd)}}
.benefits-header,.testimonials-header,.faq-header{{text-align:left;margin-bottom:72px}}
.benefits-header h2,.testimonials-header h2,.faq-header h2{{
  font-size:clamp(1.7rem,4vw,2.4rem);font-weight:200;letter-spacing:-.04em;
}}
.benefits-grid{{
  display:grid;grid-template-columns:repeat(2,1fr);
  gap:0;border-top:1px solid var(--bd);border-left:1px solid var(--bd);
}}
.benefit-card{{
  padding:48px 44px;
  border-right:1px solid var(--bd);border-bottom:1px solid var(--bd);
  background:var(--bg);transition:background .4s;
  position:relative;overflow:hidden;
}}
.benefit-card::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:var(--p);transform:scaleX(0);transform-origin:left;
  transition:transform .5s cubic-bezier(.76,0,.24,1);
}}
.benefit-card:hover{{background:var(--bg-alt)}}
.benefit-card:hover::before{{transform:scaleX(1)}}
.benefit-icon{{
  width:auto;height:auto;border-radius:0;background:none;
  font-size:1.1rem;margin-bottom:24px;display:block;
}}
.benefit-card h3{{
  font-size:.95rem;margin-bottom:12px;
  font-weight:600;letter-spacing:.02em;text-transform:uppercase;
}}
.benefit-card p{{color:var(--tx-muted);font-size:.9rem;line-height:1.9}}

/* ── Testimonials ── */
.testimonials-section{{padding:120px 0;border-top:1px solid var(--bd)}}
.testimonials-grid{{
  display:grid;grid-template-columns:repeat(3,1fr);
  gap:0;border-top:1px solid var(--bd);border-left:1px solid var(--bd);
}}
.testimonial-card{{
  padding:44px 36px;background:var(--bg);
  border-right:1px solid var(--bd);border-bottom:1px solid var(--bd);
  transition:background .3s;display:flex;flex-direction:column;
}}
.testimonial-card:hover{{background:var(--bg-alt)}}
.testimonial-stars{{
  color:var(--tx);margin-bottom:20px;letter-spacing:4px;font-size:.8rem;
}}
.testimonial-quote{{
  font-size:.95rem;line-height:2;color:var(--tx-secondary);
  margin-bottom:28px;flex:1;
}}
.testimonial-author{{display:flex;align-items:center;gap:14px}}
.author-avatar{{
  width:36px;height:36px;border-radius:50%;
  background:var(--bg-alt);border:1px solid var(--bd);
  display:flex;align-items:center;justify-content:center;
  font-family:var(--hf);font-weight:600;font-size:.78rem;color:var(--tx-secondary);
}}
.author-info .name{{font-weight:600;font-size:.85rem}}
.author-info .role{{font-size:.75rem;color:var(--tx-muted)}}

/* ── Final CTA ── */
.cta-final{{
  text-align:left;padding:128px 0;background:var(--bg);color:var(--tx);
  border-radius:0;margin:0;
  border-top:1px solid var(--bd);
}}
.cta-final::before{{display:none}}
.cta-final .container{{max-width:800px}}
.cta-final .urgency-badge{{
  background:transparent;border:1px solid var(--bd);
  color:var(--tx-muted);border-radius:0;
  font-size:.7rem;padding:6px 16px;margin-bottom:36px;
  letter-spacing:.14em;text-transform:uppercase;display:inline-block;
}}
.cta-final h2{{
  font-size:clamp(1.8rem,5vw,3rem);font-weight:200;
  margin-bottom:24px;letter-spacing:-.05em;max-width:16ch;
}}
.cta-final p{{
  color:var(--tx-muted);margin-bottom:48px;font-size:1.02rem;
  max-width:44ch;margin-left:0;line-height:2;
}}

/* ── Responsive ── */
@media(max-width:768px){{
  .hero{{padding:100px 0 80px}}
  .benefits-grid,.testimonials-grid{{grid-template-columns:1fr}}
  .transform-grid{{grid-template-columns:1fr}}
  .proof-grid{{flex-direction:column;gap:0}}
  .proof-item{{border-right:none;border-bottom:1px solid var(--bd);padding:20px 0;margin:0;width:100%}}
  .proof-item:last-child{{border-bottom:none}}
  .offer-card{{padding:36px 28px}}
  .section-text,.solution-section,.benefits-section,.transformation,.offer-section,.testimonials-section,.faq-section{{padding:72px 0}}
  .product-layout{{grid-template-columns:1fr}}
  .story-layout.with-image{{grid-template-columns:1fr}}
  .trust-badges-grid{{gap:24px}}
}}"""
    return base + "\n" + shared + "\n" + theme


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE: BOLD
# Identity: Neo-brutalism with editorial muscle. Balenciaga energy
#           meets Figma marketing. Raw, confident, unforgettable.
# Typography: Black-weight display, near-grotesque
# Motion: Hover fills, scale pops, zero subtlety
# ═══════════════════════════════════════════════════════════════════

def _css_bold(P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten):
    base   = _css_base(P, S, A, BG, TX, HF, BF, P_light)
    shared = _css_shared_components(P, S, A, BG, TX, HF, BF, P_light, _rgba)
    p_dark = S  # use secondary as dark anchor

    theme = f"""
/* ── Keyframes ── */
@keyframes marqueeBold{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
@keyframes revealUp{{
  from{{clip-path:inset(100% 0 0 0);transform:translateY(24px)}}
  to{{clip-path:inset(0% 0 0 0);transform:translateY(0)}}
}}

/* ── Buttons ── */
.btn{{
  display:inline-flex;align-items:center;justify-content:center;gap:12px;
  padding:20px 52px;font-family:var(--hf);font-weight:900;font-size:1rem;
  border-radius:0;cursor:pointer;letter-spacing:.06em;
  text-transform:uppercase;text-decoration:none;
  border:3px solid transparent;
  transition:all .25s cubic-bezier(.76,0,.24,1);
  position:relative;
}}
.btn-primary{{
  background:var(--tx);color:var(--bg);border-color:var(--tx);
}}
.btn-primary:hover{{
  background:var(--p);border-color:var(--p);color:#fff;
  transform:translate(-4px,-4px);
  box-shadow:4px 4px 0 var(--tx);
}}
.btn-white{{background:#fff;color:var(--tx);border-color:#fff}}
.btn-white:hover{{
  background:transparent;color:#fff;border-color:#fff;
  transform:translate(-4px,-4px);box-shadow:4px 4px 0 rgba(255,255,255,.4);
}}

/* ── Hero ── */
.hero{{
  position:relative;padding:200px 0 180px;text-align:center;
  background:{TX};color:{BG};overflow:hidden;
}}
.hero::before{{
  content:'';position:absolute;inset:0;
  background:repeating-linear-gradient(
    -45deg,
    transparent,transparent 40px,
    rgba(255,255,255,.025) 40px,rgba(255,255,255,.025) 41px
  );
}}
.hero::after{{display:none}}
.hero .container{{position:relative;z-index:2}}
.hero h1{{
  font-size:clamp(3.4rem,9vw,6.4rem);font-weight:900;line-height:.95;
  margin-bottom:36px;letter-spacing:-.05em;text-transform:uppercase;
  color:{BG};
}}
.hero .subtitle{{
  font-size:clamp(1.05rem,2vw,1.25rem);color:rgba(255,255,255,.65);
  max-width:560px;margin:0 auto 56px;line-height:1.75;font-weight:400;
}}
.hero .trust-line{{
  margin-top:56px;font-size:.78rem;
  color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.14em;
}}

/* ── Social Proof ── */
.social-proof{{
  padding:0;background:var(--p);color:#fff;
  overflow:hidden;border-top:3px solid {TX};border-bottom:3px solid {TX};
}}
.proof-grid{{
  display:flex;justify-content:flex-start;align-items:stretch;
  flex-wrap:nowrap;gap:0;
}}
.proof-item{{
  text-align:center;padding:40px 56px;
  border-right:3px solid rgba(255,255,255,.15);flex-shrink:0;
}}
.proof-item:last-child{{border-right:none}}
.proof-value{{
  font-family:var(--hf);font-size:2.2rem;font-weight:900;
  color:#fff;line-height:1.1;letter-spacing:-.04em;
}}
.proof-label{{
  font-size:.76rem;color:rgba(255,255,255,.7);
  margin-top:6px;text-transform:uppercase;letter-spacing:.1em;
}}
.proof-stars{{color:#FCD34D;font-size:1.1rem;letter-spacing:2px;margin-bottom:6px}}

/* ── Sections ── */
.section-text{{padding:140px 0}}
.solution-section{{background:{BG};padding:0;border-top:3px solid {TX};border-bottom:3px solid {TX};}}
.solution-section .text-block{{
  max-width:none;margin:0;padding:100px 0;
  display:grid;grid-template-columns:1fr 1fr;gap:80px;align-items:center;
}}
.text-block h2{{
  font-size:clamp(2.2rem,5.5vw,3.6rem);margin-bottom:36px;
  font-weight:900;text-transform:uppercase;letter-spacing:-.04em;
}}
.text-block p{{font-size:1.05rem;color:var(--tx-secondary);margin-bottom:24px;line-height:1.85}}
.text-block .highlight-text{{
  color:var(--tx);font-weight:900;font-size:1.15rem;
  border-left:6px solid var(--p);padding-left:20px;
  margin:40px 0;text-transform:uppercase;letter-spacing:.02em;
}}

/* ── Benefits ── */
.benefits-section{{padding:0;border-top:3px solid {TX}}}
.benefits-header,.testimonials-header,.faq-header{{
  text-align:left;margin-bottom:0;padding:80px 0 0;
}}
.benefits-header h2,.testimonials-header h2,.faq-header h2{{
  font-size:clamp(2rem,5vw,3.4rem);font-weight:900;text-transform:uppercase;
  letter-spacing:-.04em;margin-bottom:64px;
}}
.benefits-grid{{
  display:grid;grid-template-columns:repeat(2,1fr);
  gap:0;border-top:3px solid {TX};border-left:3px solid {TX};
  margin-bottom:0;
}}
.benefit-card{{
  padding:56px 48px;
  border-right:3px solid {TX};border-bottom:3px solid {TX};
  background:var(--bg);transition:background .2s,color .2s;
  position:relative;
}}
.benefit-card::before{{display:none}}
.benefit-card:hover{{background:var(--p);}}
.benefit-card:hover h3,.benefit-card:hover p{{color:#fff}}
.benefit-icon{{
  width:auto;height:auto;border-radius:0;background:none;
  font-size:2rem;margin-bottom:20px;display:block;
}}
.benefit-card h3{{
  font-size:1.05rem;margin-bottom:12px;
  font-weight:900;text-transform:uppercase;letter-spacing:.04em;
  transition:color .2s;
}}
.benefit-card p{{color:var(--tx-secondary);font-size:.92rem;line-height:1.8;transition:color .2s}}

/* ── Testimonials ── */
.testimonials-section{{
  padding:120px 0;background:var(--bg-alt);
  border-top:3px solid {TX};
}}
.testimonials-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:0}}
.testimonial-card{{
  padding:48px 40px;background:var(--bg);
  border:3px solid {TX};margin:-3px 0 0 -3px;
  display:flex;flex-direction:column;
  transition:background .2s;
}}
.testimonial-card:hover{{background:var(--bg-alt)}}
.testimonial-stars{{color:var(--amber);margin-bottom:16px;font-size:1.1rem;letter-spacing:3px}}
.testimonial-quote{{
  font-size:1rem;line-height:1.8;color:var(--tx);
  margin-bottom:24px;font-weight:500;flex:1;
}}
.testimonial-author{{display:flex;align-items:center;gap:12px}}
.author-avatar{{
  width:44px;height:44px;border-radius:0;
  background:var(--p);border:3px solid {TX};
  display:flex;align-items:center;justify-content:center;
  font-family:var(--hf);font-weight:900;font-size:.85rem;color:#fff;
}}
.author-info .name{{font-weight:900;font-size:.88rem;text-transform:uppercase;letter-spacing:.04em}}
.author-info .role{{font-size:.76rem;color:var(--tx-muted)}}

/* ── Final CTA ── */
.cta-final{{
  text-align:left;padding:0;
  background:var(--p);color:#fff;
  border-radius:0;margin:0;
  border-top:3px solid {TX};
}}
.cta-final::before{{display:none}}
.cta-final .container{{padding:120px 28px}}
.cta-final .urgency-badge{{
  background:rgba(0,0,0,.25);border:3px solid rgba(255,255,255,.3);
  border-radius:0;font-size:.76rem;font-weight:900;
  text-transform:uppercase;letter-spacing:.12em;
  padding:10px 24px;margin-bottom:36px;display:inline-block;
}}
.cta-final h2{{
  font-size:clamp(2.2rem,6vw,4rem);font-weight:900;
  margin-bottom:28px;letter-spacing:-.04em;text-transform:uppercase;
  color:#fff;max-width:16ch;
}}
.cta-final p{{
  color:rgba(255,255,255,.75);margin-bottom:52px;
  font-size:1.1rem;max-width:44ch;margin-left:0;line-height:1.85;
}}

/* ── Responsive ── */
@media(max-width:768px){{
  .hero{{padding:120px 0 100px}}
  .benefits-grid,.testimonials-grid{{grid-template-columns:1fr}}
  .transform-grid{{grid-template-columns:1fr}}
  .solution-section .text-block{{grid-template-columns:1fr;gap:40px}}
  .proof-grid{{flex-wrap:wrap}}
  .proof-item{{border-right:none;border-bottom:3px solid rgba(255,255,255,.15);width:100%}}
  .offer-card{{padding:36px 28px}}
  .section-text,.benefits-section,.transformation,.offer-section,.testimonials-section,.faq-section{{padding:80px 0}}
  .product-layout{{grid-template-columns:1fr}}
  .story-layout.with-image{{grid-template-columns:1fr}}
  .trust-badges-grid{{gap:24px}}
}}"""
    return base + "\n" + shared + "\n" + theme


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE: DARK
# Identity: Cyberpunk editorial. Like a Cyberpunk 2077 x Notion
#           collab. Deep void + surgical neon. Premium tech brand.
# Typography: Monospace accents + clean grotesque display
# Motion: Glow pulses, scanlines, neon border traces
# ═══════════════════════════════════════════════════════════════════

def _css_dark(P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten):
    BG_D     = "#050508"
    TX_D     = "#E8EAF0"
    BD_D     = "#1A1D2E"
    BG_ALT_D = "#0C0D14"
    BG_WRM_D = "#111028"

    p_glow   = _rgba(P, 0.5)
    p_neon   = _rgba(P, 0.15)
    a_glow   = _rgba(A, 0.4)
    s_glow   = _rgba(S, 0.3)

    base   = _css_base(P, S, A, BG_D, TX_D, HF, BF, P_light)
    shared = _css_shared_components(P, S, A, BG_D, TX_D, HF, BF, P_light, _rgba)

    theme = f"""
/* ── Keyframes ── */
@keyframes scanline{{
  0%{{transform:translateY(-100%)}}100%{{transform:translateY(100vh)}}
}}
@keyframes neonPulse{{
  0%,100%{{box-shadow:0 0 8px {_rgba(P,0.4)},0 0 24px {_rgba(P,0.2)}}}
  50%{{box-shadow:0 0 20px {p_glow},0 0 60px {_rgba(P,0.3)}}}
}}
@keyframes borderTrace{{
  0%{{background-position:0% 0%}}
  100%{{background-position:400% 0%}}
}}
@keyframes voidPulse{{
  0%,100%{{opacity:.5;transform:scale(1)}}
  50%{{opacity:.8;transform:scale(1.05)}}
}}

/* ── Global Dark Overrides ── */
body{{
  background:{BG_D};color:{TX_D};
  --bd:{BD_D};--bg-alt:{BG_ALT_D};--bg-warm:{BG_WRM_D};
  --tx-secondary:#7A8299;--tx-muted:#3D4157;
}}

/* ── Buttons ── */
.btn{{
  display:inline-flex;align-items:center;justify-content:center;gap:10px;
  padding:16px 44px;font-family:var(--hf);font-weight:700;font-size:.92rem;
  border-radius:10px;cursor:pointer;
  transition:all .4s cubic-bezier(.4,0,.2,1);text-decoration:none;
  position:relative;overflow:hidden;border:none;letter-spacing:.03em;
}}
.btn-primary{{
  background:var(--p);color:#fff;
  box-shadow:0 0 20px {_rgba(P,0.35)},0 4px 16px rgba(0,0,0,.5),
             inset 0 1px 0 rgba(255,255,255,.1);
  animation:neonPulse 3s ease-in-out infinite;
}}
.btn-primary:hover{{
  transform:translateY(-3px);
  box-shadow:0 0 40px {p_glow},0 8px 32px rgba(0,0,0,.6),
             inset 0 1px 0 rgba(255,255,255,.15);
}}
.btn-white{{
  background:{BD_D};color:{TX_D};
  border:1px solid rgba(255,255,255,.08);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.05);
}}
.btn-white:hover{{
  background:#1E2236;border-color:rgba(255,255,255,.16);
  transform:translateY(-3px);box-shadow:0 8px 32px rgba(0,0,0,.5);
}}

/* ── Hero ── */
.hero{{
  position:relative;padding:172px 0 148px;text-align:center;
  background:{BG_D};color:{TX_D};overflow:hidden;isolation:isolate;
}}
.hero::before{{
  content:'';position:absolute;inset:-30%;
  background:
    radial-gradient(ellipse 600px 500px at 25% 35%,{p_neon} 0%,transparent 65%),
    radial-gradient(ellipse 500px 500px at 75% 65%,{_rgba(S,0.08)} 0%,transparent 65%),
    radial-gradient(ellipse 300px 300px at 50% 90%,{_rgba(A,0.06)} 0%,transparent 65%);
  animation:voidPulse 12s ease-in-out infinite;
}}
.hero::after{{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,{_rgba(P,0.6)},transparent);
}}
.hero .container{{position:relative;z-index:2}}
.hero h1{{
  font-size:clamp(2.6rem,6.5vw,4.4rem);font-weight:900;line-height:1.04;
  margin-bottom:24px;letter-spacing:-.04em;
  background:linear-gradient(160deg,{TX_D} 0%,rgba(232,234,240,.5) 50%,{A} 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.hero .subtitle{{
  font-size:clamp(.95rem,2vw,1.15rem);color:rgba(232,234,240,.45);
  max-width:520px;margin:0 auto 48px;line-height:1.85;font-weight:400;
}}
.hero .trust-line{{margin-top:48px;font-size:.8rem;color:rgba(232,234,240,.25);letter-spacing:.06em}}

/* ── Social Proof ── */
.social-proof{{
  padding:44px 0;background:{BG_ALT_D};
  border-top:1px solid {BD_D};border-bottom:1px solid {BD_D};
}}
.proof-grid{{display:flex;justify-content:center;align-items:center;gap:64px;flex-wrap:wrap}}
.proof-item{{text-align:center}}
.proof-value{{
  font-family:var(--hf);font-size:1.8rem;font-weight:900;
  color:var(--p);line-height:1.1;
  text-shadow:0 0 20px {_rgba(P,0.5)};
}}
.proof-label{{font-size:.78rem;color:#3D4157;margin-top:6px;letter-spacing:.06em}}
.proof-stars{{color:var(--amber);font-size:1rem;letter-spacing:3px;margin-bottom:6px}}

/* ── Sections ── */
.section-text{{padding:112px 0;background:{BG_D}}}
.solution-section{{background:{BG_ALT_D};padding:112px 0}}
.text-block{{max-width:680px;margin:0 auto;text-align:center}}
.text-block h2{{
  font-size:clamp(1.8rem,4vw,2.6rem);margin-bottom:28px;color:{TX_D};
  letter-spacing:-.03em;
}}
.text-block p{{font-size:1.02rem;color:#7A8299;margin-bottom:20px;line-height:1.9}}
.text-block .highlight-text{{
  color:{TX_D};font-weight:600;font-size:1.05rem;
  border:1px solid {BD_D};border-left:3px solid var(--p);
  padding:16px 24px;margin:36px 0;text-align:left;
  background:{BG_WRM_D};border-radius:0 8px 8px 0;
}}

/* ── Benefits ── */
.benefits-section{{padding:112px 0;background:{BG_D}}}
.benefits-header,.testimonials-header,.faq-header{{text-align:center;margin-bottom:64px}}
.benefits-header h2,.testimonials-header h2,.faq-header h2{{
  font-size:clamp(1.8rem,4vw,2.6rem);color:{TX_D};letter-spacing:-.03em;
}}
.benefits-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
.benefit-card{{
  padding:40px 36px;border-radius:16px;
  border:1px solid {BD_D};background:{BG_ALT_D};
  transition:all .5s cubic-bezier(.4,0,.2,1);
  position:relative;overflow:hidden;
}}
.benefit-card::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--p),var(--a),transparent);
  background-size:200% 100%;opacity:0;
  transition:opacity .4s;animation:borderTrace 4s linear infinite paused;
}}
.benefit-card:hover{{
  border-color:rgba(255,255,255,.08);
  box-shadow:0 0 40px {_rgba(P,0.08)},0 20px 60px rgba(0,0,0,.4);
  transform:translateY(-6px);background:#0F1020;
}}
.benefit-card:hover::before{{opacity:1;animation-play-state:running}}
.benefit-icon{{
  width:52px;height:52px;border-radius:12px;
  background:{BG_WRM_D};border:1px solid {BD_D};
  display:flex;align-items:center;justify-content:center;
  font-size:1.4rem;margin-bottom:20px;
}}
.benefit-card h3{{font-size:1.08rem;margin-bottom:10px;font-weight:700;color:{TX_D}}}
.benefit-card p{{color:#7A8299;font-size:.92rem;line-height:1.8}}

/* ── Testimonials ── */
.testimonials-section{{padding:112px 0;background:{BG_ALT_D}}}
.testimonials-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.testimonial-card{{
  padding:36px 30px;border-radius:16px;
  background:{BG_D};border:1px solid {BD_D};
  transition:all .4s;display:flex;flex-direction:column;
}}
.testimonial-card:hover{{
  border-color:rgba(255,255,255,.07);
  box-shadow:0 0 30px {_rgba(P,0.07)};
}}
.testimonial-stars{{color:var(--amber);margin-bottom:16px;font-size:1rem;letter-spacing:3px}}
.testimonial-quote{{
  font-size:.94rem;line-height:1.85;color:#7A8299;
  margin-bottom:24px;flex:1;font-style:italic;
}}
.testimonial-author{{display:flex;align-items:center;gap:12px}}
.author-avatar{{
  width:40px;height:40px;border-radius:50%;
  background:linear-gradient(135deg,{P},{A});
  display:flex;align-items:center;justify-content:center;
  font-family:var(--hf);font-weight:700;font-size:.82rem;color:#fff;
  box-shadow:0 0 12px {_rgba(P,0.35)};
}}
.author-info .name{{font-weight:700;font-size:.88rem;color:{TX_D}}}
.author-info .role{{font-size:.76rem;color:#3D4157}}

/* ── Final CTA ── */
.cta-final{{
  text-align:center;padding:112px 48px;
  background:{BG_ALT_D};color:{TX_D};
  border-radius:24px;margin:64px 28px;
  position:relative;overflow:hidden;
  border:1px solid {BD_D};
}}
.cta-final::before{{
  content:'';position:absolute;inset:-20%;
  background:radial-gradient(ellipse 500px 400px at 50% 50%,{p_neon} 0%,transparent 65%);
  animation:voidPulse 10s ease-in-out infinite;
}}
.cta-final .container{{position:relative;z-index:1}}
.cta-final .urgency-badge{{
  background:{BG_WRM_D};border:1px solid {BD_D};
  border-radius:60px;font-size:.8rem;font-weight:600;
  padding:8px 20px;margin-bottom:28px;color:#7A8299;display:inline-flex;
  align-items:center;gap:8px;
}}
.cta-final h2{{
  font-size:clamp(1.8rem,4.5vw,2.8rem);font-weight:900;
  margin-bottom:20px;letter-spacing:-.04em;color:{TX_D};
}}
.cta-final p{{
  color:rgba(232,234,240,.45);margin-bottom:40px;
  font-size:1.02rem;max-width:520px;
  margin-left:auto;margin-right:auto;line-height:1.85;
}}
.footer{{background:{BG_D};border-top:1px solid {BD_D};color:#3D4157}}

/* ── Responsive ── */
@media(max-width:768px){{
  .hero{{padding:100px 0 80px}}
  .benefits-grid,.testimonials-grid{{grid-template-columns:1fr}}
  .transform-grid{{grid-template-columns:1fr}}
  .proof-grid{{gap:36px}}
  .offer-card{{padding:36px 28px}}
  .cta-final{{margin:32px 16px;padding:64px 24px}}
  .section-text,.solution-section,.benefits-section,.transformation,.offer-section,.testimonials-section,.faq-section{{padding:72px 0}}
  .product-layout{{grid-template-columns:1fr}}
  .story-layout.with-image{{grid-template-columns:1fr}}
  .trust-badges-grid{{gap:24px}}
  .countdown-timer{{gap:4px}}
  .timer-num{{font-size:1.8rem;padding:8px 14px;min-width:56px}}
}}"""
    return base + "\n" + shared + "\n" + theme


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE: ELEGANT
# Identity: Maison Margiela x Aesop. Ceremonial whitespace,
#           museum-grade typography, restrained opulence.
# Typography: Didone display (Playfair Display), Cormorant body
# Motion: Invisible — opacity fades only, 0 transform
# ═══════════════════════════════════════════════════════════════════

def _css_elegant(P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten):
    HF_E = "Playfair Display"
    BF_E = "Cormorant Garamond"

    cream    = "#FAF8F4"
    ink      = "#1C1917"
    gold     = "#B8966B"
    gold_lt  = "#F0E6D3"
    gold_mid = "#D4B896"

    base   = _css_base(P, S, A, cream, ink, HF_E, BF_E, P_light)
    shared = _css_shared_components(P, S, A, cream, ink, HF_E, BF_E, P_light, _rgba)

    theme = f"""
/* ── Import Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400;1,700&family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&display=swap');

/* ── Global Overrides ── */
body{{
  background:{cream};color:{ink};
  font-family:'{BF_E}',Georgia,serif;font-size:1.1rem;
  font-weight:300;letter-spacing:.01em;
  --bd:#E8E0D5;--bg-alt:{gold_lt};--bg-warm:{gold_lt};
  --tx-secondary:#6B5F54;--tx-muted:#A89880;
}}
h1,h2,h3,h4{{
  font-family:'{HF_E}',Georgia,serif;
  letter-spacing:-.01em;font-weight:400;
}}

/* ── Buttons ── */
.btn{{
  display:inline-flex;align-items:center;justify-content:center;gap:12px;
  padding:16px 48px;font-family:'{HF_E}',Georgia,serif;
  font-weight:400;font-size:.88rem;
  border-radius:0;cursor:pointer;
  letter-spacing:.18em;text-transform:uppercase;
  transition:all .6s cubic-bezier(.76,0,.24,1);text-decoration:none;
  border:1px solid;
}}
.btn-primary{{
  background:{gold};color:#fff;border-color:{gold};
}}
.btn-primary:hover{{
  background:transparent;color:{gold};
}}
.btn-white{{
  background:transparent;color:{cream};border-color:rgba(250,248,244,.5);
}}
.btn-white:hover{{background:rgba(250,248,244,.08);border-color:{cream}}}

/* ── Hero ── */
.hero{{
  position:relative;padding:200px 0 180px;text-align:center;
  background:{cream};color:{ink};overflow:hidden;
}}
.hero::before{{
  content:'';position:absolute;inset:0;
  background:
    radial-gradient(ellipse 800px 600px at 50% 0%,{gold_lt} 0%,transparent 70%);
}}
.hero::after{{display:none}}
.hero .container{{position:relative;z-index:2;max-width:880px}}
.hero h1{{
  font-size:clamp(2.6rem,6.5vw,4.4rem);
  font-weight:400;font-style:italic;line-height:1.18;
  margin-bottom:36px;letter-spacing:.01em;color:{ink};
}}
.hero .subtitle{{
  font-size:clamp(1.1rem,2vw,1.3rem);color:#6B5F54;
  max-width:480px;margin:0 auto 56px;line-height:2.1;
  font-weight:300;font-style:italic;
  font-family:'{BF_E}',Georgia,serif;
}}
.hero .trust-line{{
  margin-top:60px;font-size:.72rem;color:#A89880;
  letter-spacing:.22em;text-transform:uppercase;
}}

/* ── Decorative divider ── */
.hero .trust-line::before,.hero .trust-line::after{{
  content:'——';opacity:.4;margin:0 12px;
}}

/* ── Social Proof ── */
.social-proof{{
  padding:64px 0;background:{cream};
  border-top:1px solid #E8E0D5;border-bottom:1px solid #E8E0D5;
}}
.proof-grid{{display:flex;justify-content:center;align-items:center;gap:80px;flex-wrap:wrap}}
.proof-item{{text-align:center}}
.proof-value{{
  font-family:'{HF_E}',Georgia,serif;font-size:1.7rem;
  font-weight:400;font-style:italic;color:{gold};line-height:1.2;
}}
.proof-label{{
  font-size:.7rem;color:#A89880;margin-top:8px;
  text-transform:uppercase;letter-spacing:.18em;
}}
.proof-stars{{color:{gold};font-size:.9rem;letter-spacing:4px;margin-bottom:8px}}

/* ── Sections ── */
.section-text{{padding:140px 0}}
.solution-section{{
  background:{gold_lt};padding:140px 0;
  border-top:1px solid #E8E0D5;border-bottom:1px solid #E8E0D5;
}}
.text-block{{max-width:600px;margin:0 auto;text-align:center}}
.text-block h2{{
  font-size:clamp(1.7rem,3.5vw,2.6rem);margin-bottom:32px;
  font-weight:400;font-style:italic;
}}
.text-block p{{
  font-size:1.08rem;color:#6B5F54;margin-bottom:24px;line-height:2.2;
  font-family:'{BF_E}',Georgia,serif;font-weight:300;
}}
.text-block .highlight-text{{
  color:{ink};font-weight:400;font-size:1.1rem;
  border-left:1px solid {gold};padding:8px 0 8px 32px;
  margin:48px auto;text-align:left;max-width:480px;
  font-style:italic;font-family:'{HF_E}',Georgia,serif;
}}

/* ── Benefits ── */
.benefits-section{{padding:140px 0}}
.benefits-header,.testimonials-header,.faq-header{{
  text-align:center;margin-bottom:80px;
}}
.benefits-header h2,.testimonials-header h2,.faq-header h2{{
  font-size:clamp(1.7rem,3.5vw,2.6rem);font-weight:400;font-style:italic;
}}
.benefits-header h2::after,.testimonials-header h2::after,.faq-header h2::after{{
  content:'';display:block;width:40px;height:1px;
  background:{gold};margin:20px auto 0;
}}
.benefits-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:48px}}
.benefit-card{{
  padding:44px 40px;border-radius:0;border:none;
  border-top:1px solid #E8E0D5;background:transparent;
  transition:background .5s;
}}
.benefit-card::before{{display:none}}
.benefit-card:hover{{background:{gold_lt}}}
.benefit-icon{{
  font-size:1.1rem;margin-bottom:20px;display:block;
  color:{gold};
}}
.benefit-card h3{{
  font-size:1.05rem;margin-bottom:14px;
  font-family:'{HF_E}',Georgia,serif;font-weight:700;
  letter-spacing:.01em;
}}
.benefit-card p{{
  color:#6B5F54;font-size:.97rem;line-height:2;
  font-family:'{BF_E}',Georgia,serif;font-weight:300;
}}

/* ── Testimonials ── */
.testimonials-section{{
  padding:140px 0;background:{gold_lt};
  border-top:1px solid #E8E0D5;
}}
.testimonials-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:40px}}
.testimonial-card{{
  padding:44px 36px;background:{cream};
  border:1px solid #E8E0D5;
  display:flex;flex-direction:column;
  transition:box-shadow .5s;
}}
.testimonial-card:hover{{box-shadow:0 8px 40px rgba(184,150,107,.12)}}
.testimonial-stars{{color:{gold};margin-bottom:20px;letter-spacing:5px;font-size:.85rem}}
.testimonial-quote{{
  font-size:1rem;line-height:2.1;color:#6B5F54;
  margin-bottom:28px;font-style:italic;flex:1;
  font-family:'{BF_E}',Georgia,serif;font-weight:300;
}}
.testimonial-author{{display:flex;align-items:center;gap:14px}}
.author-avatar{{
  width:40px;height:40px;border-radius:50%;
  background:{gold_mid};
  display:flex;align-items:center;justify-content:center;
  font-family:'{HF_E}',Georgia,serif;font-weight:400;
  font-size:.85rem;color:{cream};font-style:italic;
}}
.author-info .name{{
  font-weight:600;font-size:.88rem;
  font-family:'{HF_E}',Georgia,serif;
}}
.author-info .role{{font-size:.76rem;color:#A89880}}

/* ── Final CTA ── */
.cta-final{{
  text-align:center;padding:160px 48px;
  background:{ink};color:{cream};
  border-radius:0;margin:0;
}}
.cta-final::before{{display:none}}
.cta-final .urgency-badge{{
  background:rgba(250,248,244,.06);border:1px solid rgba(250,248,244,.15);
  border-radius:0;font-size:.7rem;padding:8px 24px;margin-bottom:40px;
  letter-spacing:.18em;text-transform:uppercase;display:inline-block;
  font-family:'{BF_E}',Georgia,serif;
  color:rgba(250,248,244,.5);
}}
.cta-final h2{{
  font-size:clamp(1.8rem,4.5vw,3rem);font-weight:400;
  margin-bottom:28px;font-style:italic;letter-spacing:.01em;
  color:{cream};
}}
.cta-final h2::after{{
  content:'';display:block;width:40px;height:1px;
  background:{gold};margin:20px auto 0;
}}
.cta-final p{{
  color:rgba(250,248,244,.55);margin-bottom:52px;
  font-size:1.08rem;max-width:440px;
  margin-left:auto;margin-right:auto;line-height:2.2;
  font-family:'{BF_E}',Georgia,serif;font-weight:300;font-style:italic;
}}
.footer{{
  background:{cream};border-top:1px solid #E8E0D5;
  color:#A89880;font-family:'{BF_E}',Georgia,serif;font-weight:300;
}}

/* ── Responsive ── */
@media(max-width:768px){{
  .hero{{padding:120px 0 100px}}
  .benefits-grid,.testimonials-grid{{grid-template-columns:1fr}}
  .transform-grid{{grid-template-columns:1fr}}
  .proof-grid{{gap:48px}}
  .offer-card{{padding:36px 28px}}
  .cta-final{{padding:100px 24px}}
  .section-text,.solution-section,.benefits-section,.transformation,.offer-section,.testimonials-section,.faq-section{{padding:80px 0}}
  .product-layout{{grid-template-columns:1fr}}
  .story-layout.with-image{{grid-template-columns:1fr}}
  .trust-badges-grid{{gap:24px}}
}}"""
    return base + "\n" + shared + "\n" + theme


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE: ECOMMERCE
# Identity: Conversion-engineered warmth. Think Allbirds x Glossier.
#           Trustworthy, warm, tactile. Every element earns its place.
# Typography: Rounded display + legible body — approachable authority
# Motion: Subtle lifts, badge pulses, sticky urgency
# ═══════════════════════════════════════════════════════════════════

def _css_ecommerce(P, S, A, BG, TX, HF, BF, P_light, _rgba, _lighten):
    base   = _css_base(P, S, A, BG, TX, HF, BF, P_light)
    shared = _css_shared_components(P, S, A, BG, TX, HF, BF, P_light, _rgba)

    p_shadow = _rgba(P, 0.2)
    p_glass  = _rgba(P, 0.06)
    warm_bg  = "#FBF9F7"
    warm_bd  = "#EDE8E1"

    theme = f"""
/* ── Global Overrides ── */
body{{
  --bd:{warm_bd};--bg-alt:{warm_bg};--bg-warm:#F0EBE3;
  --tx-secondary:#6B6056;--tx-muted:#A89C90;
}}

/* ── Keyframes ── */
@keyframes trustPulse{{
  0%,100%{{transform:scale(1)}}50%{{transform:scale(1.04)}}
}}
@keyframes stickySlide{{
  from{{transform:translateY(-100%);opacity:0}}to{{transform:translateY(0);opacity:1}}
}}

/* ── Buttons ── */
.btn{{
  display:inline-flex;align-items:center;justify-content:center;gap:10px;
  padding:18px 44px;font-family:var(--hf);font-weight:700;font-size:.97rem;
  border-radius:100px;border:none;cursor:pointer;
  transition:all .35s cubic-bezier(.4,0,.2,1);text-decoration:none;
  position:relative;overflow:hidden;letter-spacing:.01em;
}}
.btn-primary{{
  background:var(--p);color:#fff;
  box-shadow:0 4px 20px {p_shadow},0 1px 4px rgba(0,0,0,.1);
}}
.btn-primary:hover{{
  transform:translateY(-3px);
  box-shadow:0 10px 32px {p_shadow},0 4px 12px rgba(0,0,0,.08);
  filter:brightness(1.05);
}}
.btn-white{{
  background:#fff;color:var(--tx);
  border:1.5px solid {warm_bd};
  box-shadow:0 2px 8px rgba(0,0,0,.06);
}}
.btn-white:hover{{
  border-color:var(--p);color:var(--p);
  box-shadow:0 4px 20px {p_shadow};transform:translateY(-2px);
}}

/* ── Hero ── */
.hero{{
  padding:100px 0 96px;background:{warm_bg};
  color:var(--tx);overflow:hidden;
  border-bottom:1px solid {warm_bd};
}}
.hero::before,.hero::after{{display:none}}
.hero .container{{
  display:grid;grid-template-columns:1fr 1fr;
  gap:64px;align-items:center;max-width:var(--mw);
}}
.hero h1{{
  font-size:clamp(2rem,4.5vw,3.2rem);font-weight:800;
  line-height:1.1;margin-bottom:20px;letter-spacing:-.035em;
}}
.hero h1 em{{font-style:normal;color:var(--p)}}
.hero .subtitle{{
  font-size:1.02rem;color:var(--tx-secondary);
  max-width:42ch;margin:0 0 36px;line-height:1.85;
}}
.hero .trust-line{{
  margin-top:36px;font-size:.82rem;color:var(--tx-muted);
  display:flex;align-items:center;gap:8px;
}}
.hero .trust-line::before{{
  content:'✓';color:var(--success);font-weight:700;
}}

/* ── Social Proof ── */
.social-proof{{
  padding:36px 0;background:#fff;
  border-bottom:1px solid {warm_bd};
}}
.proof-grid{{display:flex;justify-content:center;align-items:center;gap:48px;flex-wrap:wrap}}
.proof-item{{text-align:center}}
.proof-value{{
  font-family:var(--hf);font-size:1.5rem;font-weight:800;
  color:var(--p);line-height:1.15;letter-spacing:-.02em;
}}
.proof-label{{font-size:.75rem;color:var(--tx-muted);margin-top:4px}}
.proof-stars{{color:var(--amber);font-size:1rem;letter-spacing:2px;margin-bottom:4px}}

/* ── Sections ── */
.section-text{{padding:96px 0}}
.solution-section{{background:{warm_bg};padding:96px 0;border-top:1px solid {warm_bd}}}
.text-block{{max-width:640px;margin:0 auto}}
.text-block h2{{font-size:clamp(1.6rem,3vw,2.2rem);margin-bottom:20px;letter-spacing:-.03em}}
.text-block p{{font-size:1rem;color:var(--tx-secondary);margin-bottom:16px;line-height:1.9}}
.text-block .highlight-text{{
  color:var(--tx);font-weight:600;font-size:1.02rem;
  background:{p_glass};border:1px solid {_rgba(P,0.12)};
  border-radius:12px;padding:16px 20px;margin:28px 0;
}}

/* ── Benefits ── */
.benefits-section{{padding:96px 0}}
.benefits-header,.testimonials-header,.faq-header{{text-align:center;margin-bottom:52px}}
.benefits-header h2,.testimonials-header h2,.faq-header h2{{
  font-size:clamp(1.6rem,3vw,2.2rem);letter-spacing:-.03em;
}}
.benefits-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}
.benefit-card{{
  padding:32px 28px;border-radius:20px;
  border:1.5px solid {warm_bd};background:#fff;
  transition:all .4s cubic-bezier(.4,0,.2,1);text-align:center;
}}
.benefit-card::before{{display:none}}
.benefit-card:hover{{
  border-color:var(--p);transform:translateY(-5px);
  box-shadow:0 16px 48px {p_shadow};background:#fff;
}}
.benefit-icon{{
  width:52px;height:52px;border-radius:16px;
  background:{warm_bg};border:1px solid {warm_bd};
  display:flex;align-items:center;justify-content:center;
  font-size:1.4rem;margin:0 auto 18px;
  transition:background .3s;
}}
.benefit-card:hover .benefit-icon{{background:{p_glass};border-color:{_rgba(P,0.2)}}}
.benefit-card h3{{font-size:.97rem;margin-bottom:10px;font-weight:700;letter-spacing:-.01em}}
.benefit-card p{{color:var(--tx-secondary);font-size:.88rem;line-height:1.75}}

/* ── Testimonials ── */
.testimonials-section{{padding:96px 0;background:{warm_bg};border-top:1px solid {warm_bd}}}
.testimonials-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}
.testimonial-card{{
  padding:32px 28px;border-radius:20px;background:#fff;
  border:1.5px solid {warm_bd};
  box-shadow:0 2px 12px rgba(0,0,0,.04);
  transition:all .35s;display:flex;flex-direction:column;
}}
.testimonial-card:hover{{
  box-shadow:0 12px 40px rgba(0,0,0,.08);
  transform:translateY(-4px);border-color:var(--p);
}}
.testimonial-stars{{color:var(--amber);margin-bottom:14px;font-size:1rem;letter-spacing:2px}}
.testimonial-quote{{
  font-size:.92rem;line-height:1.85;color:#374151;
  margin-bottom:20px;font-style:italic;flex:1;
}}
.testimonial-author{{display:flex;align-items:center;gap:10px}}
.author-avatar{{
  width:38px;height:38px;border-radius:50%;
  background:linear-gradient(135deg,{A},{P});
  display:flex;align-items:center;justify-content:center;
  font-family:var(--hf);font-weight:700;font-size:.8rem;color:#fff;
}}
.author-info .name{{font-weight:700;font-size:.85rem}}
.author-info .role{{font-size:.75rem;color:var(--tx-muted)}}

/* ── Final CTA ── */
.cta-final{{
  text-align:center;padding:80px 48px;
  background:var(--p);color:#fff;
  border-radius:28px;margin:48px 28px;
  position:relative;overflow:hidden;
}}
.cta-final::before{{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 400px 300px at 80% 20%,rgba(255,255,255,.12) 0%,transparent 70%);
}}
.cta-final .container{{position:relative;z-index:1}}
.cta-final .urgency-badge{{
  background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);
  border-radius:100px;font-size:.8rem;font-weight:700;
  padding:8px 20px;margin-bottom:24px;display:inline-block;
  animation:trustPulse 2.5s ease-in-out infinite;
}}
.cta-final h2{{
  font-size:clamp(1.6rem,3.5vw,2.4rem);font-weight:800;
  margin-bottom:16px;letter-spacing:-.03em;
}}
.cta-final p{{
  color:rgba(255,255,255,.8);margin-bottom:36px;
  font-size:1rem;max-width:480px;
  margin-left:auto;margin-right:auto;line-height:1.8;
}}

/* ── Responsive ── */
@media(max-width:768px){{
  .hero .container{{grid-template-columns:1fr;gap:40px}}
  .hero{{padding:72px 0;text-align:center}}
  .hero .subtitle{{margin:0 auto 36px}}
  .hero .trust-line{{justify-content:center}}
  .benefits-grid,.testimonials-grid{{grid-template-columns:1fr}}
  .transform-grid{{grid-template-columns:1fr}}
  .proof-grid{{gap:28px}}
  .offer-card{{padding:32px 24px}}
  .cta-final{{margin:28px 16px;padding:56px 24px;border-radius:20px}}
  .section-text,.solution-section,.benefits-section,.transformation,.offer-section,.testimonials-section,.faq-section{{padding:64px 0}}
  .product-layout{{grid-template-columns:1fr}}
  .story-layout.with-image{{grid-template-columns:1fr}}
  .trust-badges-grid{{gap:24px}}
}}"""
    return base + "\n" + shared + "\n" + theme


# ═══════════════════════════════════════════════════════════════════
# TEMPLATE MAP
# ═══════════════════════════════════════════════════════════════════

_TEMPLATE_MAP = {
    "modern":    _css_modern,
    "minimal":   _css_minimal,
    "bold":      _css_bold,
    "dark":      _css_dark,
    "elegant":   _css_elegant,
    "ecommerce": _css_ecommerce,
}
