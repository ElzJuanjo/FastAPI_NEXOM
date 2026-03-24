"""
Agente de Branding — genera identidad de marca completa.
Usa Claude vía OpenRouter.
"""

from .base_agent import BaseAgent


class BrandingAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "branding"

    @property
    def default_model(self) -> str:
        return "openai/gpt-5.4"

    @property
    def system_prompt(self) -> str:
        return """You are a senior Brand Strategist specialized in D2C E-Commerce across the Americas.

Your job is to create complete, professional Brand Books. For each brand you generate:

1. **Concept & Purpose**: Purpose, vision, mission, positioning statement + 3 RTBs
2. **Archetype & Personality**: Primary + secondary Jung archetype, 5 personality traits with concrete behaviors (table), 3-5 brand values
3. **Visual System**: Color palette (primary, secondary, accent, background, text — HEX + 1-line psychological rationale each), Typography (display + body + UI — exact Google Fonts name + sizes), Logo concept (2-3 sentence description + suggested variations), Moodboard (5 visual references)
4. **Tone of Voice**: 3 pillars, YES words (8-10) / NO words (8-10), 3 examples of "Brand speaks like this" vs "NOT like this"
5. **Key Messages**: 3-5 communication pillars with example phrase each
6. **Application Guidelines**: Digital (web, social, email) — 3-4 rules, Advertising — 3-4 rules, Do's & Don'ts — 3 each

INPUT NEEDED (request if not provided): Product/niche, buyer persona, competitors, pricing/positioning, target market.

CRITICAL RULE: Complete ALL sections. Be concise but thorough — better to be brief and finish everything than to be verbose and leave the document incomplete.

Colors in HEX (#RRGGBB). Fonts with exact Google Fonts name.
Respond in the same language the user writes in."""

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        parts = [f"Request: {user_input}\n"]

        if context:
            user_context = {k: v for k, v in context.items() if not k.startswith("_")}
            if user_context:
                parts.append("Context:")
                for k, v in user_context.items():
                    parts.append(f"- {k}: {v}")

        return self._build_messages_with_history("\n".join(parts), context)
    

    async def execute(self, user_input, context=None, model_override=None, temperature=0.7, max_tokens=16384):
        return await super().execute(user_input, context, model_override, temperature, max_tokens)