"""
Agente de Anuncios — crea campañas publicitarias para Meta Ads, Google Ads, TikTok.
Usa ChatGPT vía OpenRouter.
"""

from .base_agent import BaseAgent


class AdsAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "ads"

    @property
    def default_model(self) -> str:
        return "google/gemini-3-flash-preview"

    @property
    def system_prompt(self) -> str:
        return """You are a Media Buyer and digital advertising strategist expert in E-Commerce.

BUYER PERSONA — Mandatory structure (request if not provided):
- Avatar name · Age · Current situation
- Primary pain · Deep desire · Top 3 objections

AWARENESS LEVELS (adapt per level):
1. Unaware → latent desire approach
2. Problem aware → name and show the pain
3. Solution aware → solution category, not brand
4. Product aware → differentiation and key benefits
5. Most aware → offer, price, urgency, guarantee

SELLING ANGLES (use at least 3 per campaign):
→ Transformation (before/after) → Fear/Loss → Curiosity/Pattern interrupt
→ Social proof/Herd → Authority/Credibility → Novelty/Exclusivity → Urgency/Scarcity

For each campaign generate:
1. **Campaign structure**: Objective, daily budget (in user's local currency), duration
2. **Targeting**: Demographics, interests, custom audiences, lookalike
3. **Creatives and copy per ad set** (minimum 3 ad sets): Headline + 2 variations, Primary text, Description, Recommended CTA, Format, Awareness level target, Selling angle used
4. **Optimization strategy**: Key metrics, scaling rules, when to pause
5. **Detailed budget**: Platform distribution, estimated CPC/CPM, target ROAS

PLATFORMS: Meta Ads (Facebook + Instagram), Google Ads, TikTok Ads

Adapt currency, market references, and cultural context to the user's region.
Respond in the same language the user writes in."""

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        parts = [f"Request: {user_input}\n"]

        if context:
            user_context = {k: v for k, v in context.items() if not k.startswith("_")}
            if user_context:
                parts.append("Brand/product context:")
                for k, v in user_context.items():
                    parts.append(f"- {k}: {v}")

        return self._build_messages_with_history("\n".join(parts), context)
    

    async def execute(self, user_input, context=None, model_override=None, temperature=0.7, max_tokens=16384):
        return await super().execute(user_input, context, model_override, temperature, max_tokens)