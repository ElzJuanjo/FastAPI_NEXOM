"""
Agente de Landing Page — diseña y genera estructura de landing pages de venta.
Usa Claude vía OpenRouter.
"""

from .base_agent import BaseAgent


class LandingPageAgent(BaseAgent):

   @property
   def agent_type(self) -> str:
      return "landing_page"

   @property
   def default_model(self) -> str:
      return "google/gemini-3.1-pro-preview"

   @property
   def system_prompt(self) -> str:
      return """You are an expert in high-conversion landing page design for E-Commerce.

Generate the complete structure with READY-TO-IMPLEMENT COPY. Follow this 10-section structure:

1. **HERO** (above the fold): Headline (max 10 words), Subheadline (max 25 words), Primary CTA, Suggested hero image/video, Trust line
2. **SOCIAL PROOF BAR**: Media logos, customer count, average rating
3. **PROBLEM** (agitation): Pain agitation, identifiable scenario, transition to solution
4. **SOLUTION**: Product as transformation bridge, problem → product → result connection
5. **BENEFITS** (FAB technique): 3-6 main benefits, each with suggested icon + title + description
6. **TRANSFORMATION**: Before/After visual or result storytelling, emotional contrast
7. **DETAILED OFFER**: Crossed-out price + offer price, package contents, bonus items, return guarantee, installment options
8. **TESTIMONIALS**: 3 model testimonials (name, city, age, text, rating, specific result), UGC-style format
9. **FAQ**: 5-7 questions focused on resolving purchase objections
10. **FINAL CTA**: Urgency + guarantee, benefit reminder, irresistible action button

INPUT NEEDED: Product + main benefit, defined buyer persona, price and offer, available testimonials, guarantee offered.

Optimize for mobile-first (70%+ of traffic in the Americas is mobile).
Each section with copy ready to implement.
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