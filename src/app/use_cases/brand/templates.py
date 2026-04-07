"""Templates de brand identity predefinidos por nicho/industria."""

BRAND_TEMPLATES: list[dict] = [
    {
        "id": "skincare_premium",
        "name": "Skincare Premium",
        "industry": "Belleza & Skincare",
        "color_palette": {
            "primary": "#7C3AED", "secondary": "#3E1B48",
            "accent": "#F0ABFC", "background": "#FDFAFF", "text": "#1A0A2E",
        },
        "typography": {"heading_font": "Playfair Display", "body_font": "Inter"},
        "tones": ["Científico", "Elegante", "Empático", "Confiable"],
        "key_messages": [
            "Fórmulas respaldadas por dermatología clínica",
            "Resultados visibles en 14 días",
        ],
    },
    {
        "id": "fitness_energy",
        "name": "Fitness & Energía",
        "industry": "Fitness & Suplementos",
        "color_palette": {
            "primary": "#EF4444", "secondary": "#1C1917",
            "accent": "#F97316", "background": "#FFFBF5", "text": "#1C1917",
        },
        "typography": {"heading_font": "Montserrat", "body_font": "DM Sans"},
        "tones": ["Motivacional", "Directo", "Enérgico", "Aspiracional"],
        "key_messages": [
            "Transforma tu cuerpo en 90 días",
            "Ingredientes premium, resultados reales",
        ],
    },
    {
        "id": "tech_saas",
        "name": "Tech / SaaS",
        "industry": "Tecnología",
        "color_palette": {
            "primary": "#3B82F6", "secondary": "#0F172A",
            "accent": "#06B6D4", "background": "#F8FAFC", "text": "#0F172A",
        },
        "typography": {"heading_font": "Plus Jakarta Sans", "body_font": "Inter"},
        "tones": ["Profesional", "Innovador", "Claro", "Confiable"],
        "key_messages": [
            "Automatiza lo repetitivo, enfócate en crecer",
            "Integración en minutos, resultados inmediatos",
        ],
    },
    {
        "id": "food_artisanal",
        "name": "Alimentos Artesanales",
        "industry": "Food & Beverage",
        "color_palette": {
            "primary": "#B45309", "secondary": "#451A03",
            "accent": "#D97706", "background": "#FFFBEB", "text": "#1C1917",
        },
        "typography": {"heading_font": "Libre Baskerville", "body_font": "Lato"},
        "tones": ["Artesanal", "Auténtico", "Cálido", "Cercano"],
        "key_messages": [
            "Hecho a mano con ingredientes locales",
            "Del campo a tu mesa, sin intermediarios",
        ],
    },
    {
        "id": "fashion_streetwear",
        "name": "Streetwear / Moda Urbana",
        "industry": "Moda",
        "color_palette": {
            "primary": "#000000", "secondary": "#18181B",
            "accent": "#FBBF24", "background": "#FAFAFA", "text": "#09090B",
        },
        "typography": {"heading_font": "Oswald", "body_font": "Space Grotesk"},
        "tones": ["Rebelde", "Auténtico", "Urbano", "Bold"],
        "key_messages": [
            "No sigas tendencias, créalas",
            "Estilo que habla por ti",
        ],
    },
]


def get_brand_templates() -> list[dict]:
    return BRAND_TEMPLATES


def get_template_by_id(template_id: str) -> dict | None:
    return next((t for t in BRAND_TEMPLATES if t["id"] == template_id), None)