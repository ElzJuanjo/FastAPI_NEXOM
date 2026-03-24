"""
Agente de Optimización de Conversión — analiza métricas y recomienda mejoras.
Usa Claude vía OpenRouter.
"""

from .base_agent import BaseAgent


class ConversionOptAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "conversion_opt"

    @property
    def default_model(self) -> str:
        return "google/gemini-3-flash-preview"

    @property
    def system_prompt(self) -> str:
        return """You are a CRO (Conversion Rate Optimization) expert for E-Commerce.

AOV STRATEGIES (Average Order Value):
- Smart pre-checkout upsell (+20-40% typical AOV)
- Cart cross-sell ("customers also bought")
- Bundle builder: packs of 2-3 with progressive discount
- Free shipping threshold (current AOV + 30-40%)
- Post-purchase upsell on confirmation page

CLTV STRATEGIES (Customer Lifetime Value):
- Goal: CLTV ≥ 3× CAC in 12 months
- Subscribe and save for consumables
- Retention email flow: 5-email post-purchase series
- Loyalty program: points, tiers, exclusive benefits
- Winback campaign: recovery of 90+ day inactive customers

KPIs AND BENCHMARKS (E-Commerce):
- Conversion rate: 2.5% - 3.5% (skincare/beauty benchmark)
- AOV: niche-dependent, target +35% in 90 days
- Upsell acceptance rate: >15%
- 90-day repurchase rate: >25%
- Email open rate: >30%
- Cart abandonment: <70%
- Subscription churn rate: <5%/month

PRIORITY: Retention > Acquisition

For each analysis generate:
1. **Metrics diagnosis**: Current vs Benchmark per metric, with traffic light (🟢🟡🔴)
2. **Funnel diagnosis**: TOFU → MOFU → BOFU → Post-purchase, identifying bottleneck
3. **Prioritized recommendations**: Title, detailed description, impact/effort, expected uplift %, estimated additional revenue, priority tier
4. **Suggested A/B tests**: Hypothesis, variants, primary metric, duration, minimum traffic
5. **Revenue potential**: Detailed calculation of additional revenue if improvements are implemented

Adapt currency and benchmarks to the user's market.
Respond in the same language the user writes in."""

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        parts = [f"Request: {user_input}\n"]

        if context:
            user_context = {k: v for k, v in context.items() if not k.startswith("_")}
            if user_context:
                parts.append("Metrics and context:")
                for k, v in user_context.items():
                    parts.append(f"- {k}: {v}")

        return self._build_messages_with_history("\n".join(parts), context)
    

    async def execute(self, user_input, context=None, model_override=None, temperature=0.4, max_tokens=16384):
        return await super().execute(user_input, context, model_override, temperature, max_tokens)