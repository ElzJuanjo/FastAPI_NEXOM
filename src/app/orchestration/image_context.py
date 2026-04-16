"""
Shared helpers for resolving input images (URL → base64) and analyzing
them with a vision model, so that the information can be injected into
any agent's textual input.

Both the chat executor (`executor_node`) and the flow executor
(`flow_executor`) rely on these utilities so that reference images
behave consistently across modes:

  • In chat, the user uploads an image and the router + executor analyze
    it, enrich the vague text input, and pass the base64 image as
    multimodal content to the selected agent.
  • In flows, the same resolution + analysis must happen so the flow's
    agents (product_search, copywriting, branding, landing_page, ads,
    image_gen) receive both the image AND a textual hint of what the
    image represents. Without this, multimodal LLMs may silently ignore
    the image or fail to correlate it with the prompt — which is the
    user-reported bug of "the reference image doesn't work in flows".

Key design decision: we DO NOT persist anything to S3 here. The chat
mode doesn't persist either — only the batch/creative pipelines do. The
flow just needs the in-memory base64 + textual description, which the
agents consume per request.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def resolve_images_to_base64(image_urls: list[str]) -> list[str]:
    """
    Download image URLs and convert to base64 data URIs.
    Pass-through for strings that are already base64 data URIs.
    Safe on empty / None inputs.
    """
    if not image_urls:
        return []

    from infra.tools.openrouter_client import openrouter_client

    resolved: list[str] = []
    for url in image_urls:
        if not url:
            continue
        if url.startswith("data:"):
            resolved.append(url)
            continue
        try:
            b64 = await openrouter_client._download_image_as_base64(url)
            if b64:
                resolved.append(b64)
                logger.info(f"Image resolved to base64: {url[:80]}...")
            else:
                logger.warning(f"Image resolution returned None: {url[:80]}")
        except Exception as e:
            logger.warning(f"Image resolution error: {e} for {url[:80]}")

    return resolved


async def analyze_image(b64_image: str) -> dict:
    """
    Use a vision model to describe the image. Returns a dict with:
      - search_query: short e-commerce search query
      - product_name: identified product (with brand if visible)
      - category: one-word category
      - description: detailed visual description

    Returns {} if the call fails or produces no parsable result.
    """
    from infra.tools.openrouter_client import openrouter_client

    try:
        result = await openrouter_client.chat_completion(
            model="google/gemini-3-flash-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": b64_image}},
                    {
                        "type": "text",
                        "text": (
                            "Analyze this image and respond with EXACTLY this format "
                            "(no markdown, no extra text):\n\n"
                            "SEARCH_QUERY: [a short 3-8 word product search query for "
                            "e-commerce sites, include brand and model if visible, "
                            "e.g. 'Rolex Daytona gold black dial']\n"
                            "PRODUCT_NAME: [specific product name with brand if identifiable]\n"
                            "CATEGORY: [one word: electronics|fashion|accessories|home|"
                            "beauty|sports|food|toys|other]\n"
                            "DESCRIPTION: [detailed visual description under 100 words: "
                            "colors, materials, shape, distinguishing features, "
                            "estimated price range]\n"
                        ),
                    },
                ],
            }],
            temperature=0.1,
            max_tokens=400,
        )
        raw = (result.get("content") or "").strip()
        if not raw:
            return {}

        analysis: dict = {}
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("SEARCH_QUERY:"):
                analysis["search_query"] = line.split(":", 1)[1].strip()
            elif line.startswith("PRODUCT_NAME:"):
                analysis["product_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("CATEGORY:"):
                analysis["category"] = line.split(":", 1)[1].strip()
            elif line.startswith("DESCRIPTION:"):
                analysis["description"] = line.split(":", 1)[1].strip()

        if analysis:
            logger.info(
                f"Image analyzed: query='{analysis.get('search_query', '')}' "
                f"name='{analysis.get('product_name', '')}'"
            )
        return analysis

    except Exception as e:
        logger.warning(f"Image analysis failed: {e}")
        return {}


def build_image_hint_for_agent(analysis: dict, agent_type: str) -> str:
    """
    Given an image analysis dict and the target agent type, build a
    short textual hint to append to the agent's prompt so the LLM knows
    what the reference image depicts.

    Returns an empty string if there's nothing useful to inject.
    """
    if not analysis:
        return ""

    product_name = (analysis.get("product_name") or "").strip()
    search_query = (analysis.get("search_query") or "").strip()
    description = (analysis.get("description") or "").strip()
    category = (analysis.get("category") or "").strip()

    # Nothing to inject
    if not (product_name or search_query or description):
        return ""

    if agent_type == "product_search":
        # product_search's scraper uses the textual query — the image
        # alone is not enough; we must surface the detected search_query.
        bits = []
        if search_query:
            bits.append(f"Search query from reference image: {search_query}")
        if product_name:
            bits.append(f"Identified product: {product_name}")
        if description:
            bits.append(f"Visual description: {description}")
        return "\n".join(bits)

    if agent_type == "image_gen":
        # image_gen uses the base64 reference directly; text hint just
        # sharpens the prompt so the generator knows the subject.
        if product_name and description:
            return f"Reference product: {product_name}. {description}"
        if product_name:
            return f"Reference product: {product_name}."
        if description:
            return f"Reference image description: {description}"
        return ""

    if agent_type in ("copywriting", "ads", "landing_page"):
        # Copy/ads/landing need to know WHAT to sell.
        bits = []
        if product_name:
            bits.append(f"Product from reference image: {product_name}")
            if category:
                bits[-1] += f" ({category})"
        if description:
            bits.append(f"Visual/physical details: {description}")
        return "\n".join(bits)

    if agent_type == "branding":
        bits = []
        if product_name:
            bits.append(f"Reference product for brand direction: {product_name}")
        if description:
            bits.append(f"Visual cues: {description}")
        return "\n".join(bits)

    # general fallback (store_dev, conversion_opt, dropi_connector, etc.)
    bits = []
    if product_name:
        bits.append(f"Reference image shows: {product_name}")
    if description:
        bits.append(description)
    return ". ".join(bits)
