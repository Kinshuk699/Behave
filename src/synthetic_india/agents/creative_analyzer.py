"""
Creative Analyzer Agent — extracts structured creative cards from raw ad inputs.

This is the normalization boundary of the entire system. If creative
extraction is lossy or inconsistent, every downstream judgment degrades.
"""

from __future__ import annotations

import uuid
from typing import Optional

from synthetic_india.agents.llm_client import LLMResponse, call_anthropic
from synthetic_india.config import LLMConfig, get_llm_config
from synthetic_india.schemas.creative import CreativeCard, CreativeUpload


CREATIVE_ANALYSIS_SYSTEM = """You are a marketing creative analyst specializing in Indian D2C brands. Your job is to extract structured information from ad creatives.

You analyze marketing creatives (ad images, landing pages, social media posts) and extract a structured creative card capturing all persuasion elements, pricing signals, emotional hooks, and visual characteristics.

Be precise and factual. Only extract what is actually present in the creative — do not infer or hallucinate elements that are not visible."""


CREATIVE_ANALYSIS_PROMPT = """Analyze this marketing creative and extract a structured creative card.

Brand: {brand}
Category: {category}
Format: {format}

Creative content to analyze:
{content}

Extract the following fields as a JSON object:

{{
  "headline": "Primary headline or hook text (null if not present)",
  "body_copy": "Supporting body text (null if not present)",
  "cta_text": "Call-to-action text like 'Shop Now', 'Learn More' (null if not present)",
  "cta_type": "buy | learn_more | sign_up | download | null",
  "price_shown": null or number,
  "original_price": null or number,
  "discount_percentage": null or number,
  "price_framing": "premium | value | discount | comparison | no_price",
  "urgency_cues": ["list of urgency signals like 'Limited time', 'Only 3 left'"],
  "social_proof_cues": ["list like '10K+ reviews', 'As seen on Shark Tank'"],
  "trust_signals": ["list like 'Dermatologist tested', 'ISO certified'"],
  "emotional_hooks": ["list like 'For your family', 'Be the best version'"],
  "visual_style": "minimal | bold_graphic | lifestyle | product_focused | ugc_style | celeb_endorsement | traditional | modern",
  "color_dominant": "primary color or null",
  "product_visibility": 0.0 to 1.0,
  "human_presence": true/false,
  "celebrity_present": true/false,
  "language_primary": "English | Hindi | etc.",
  "language_secondary": null or language,
  "code_mixed": true/false (Hinglish or multi-language mixing),
  "festival_context": "Diwali | Holi | Eid | Navratri | Christmas | null (only if festival imagery, messaging, or sale tie-in is present)",
  "target_city_tier": "Tier 1 | Tier 2-3 | Metro | Pan-India | null (infer from pricing, language, and positioning)",
  "cultural_references": ["list of Indian cultural motifs: 'rangoli', 'haldi', 'Bollywood', 'cricket', 'joint family', 'diyas', etc."]
}}

Return ONLY the JSON object, no explanation."""


async def analyze_creative(
    upload: CreativeUpload,
    config: Optional[LLMConfig] = None,
) -> tuple[CreativeCard, LLMResponse]:
    """
    Extract a structured creative card from a raw creative upload.

    Args:
        upload: Raw creative upload with text/image content
        config: LLM configuration

    Returns:
        Tuple of (CreativeCard, LLMResponse) for tracking
    """
    config = config or get_llm_config()

    # Build content from available sources
    content_parts = []
    if upload.raw_text:
        content_parts.append(f"Ad copy / text content:\n{upload.raw_text}")
    if upload.image_url:
        content_parts.append(f"Image URL: {upload.image_url}")
    if upload.file_path:
        content_parts.append(f"File: {upload.file_path}")

    content = "\n\n".join(content_parts) if content_parts else "No content provided"

    prompt = CREATIVE_ANALYSIS_PROMPT.format(
        brand=upload.brand,
        category=upload.category,
        format=upload.format,
        content=content,
    )

    response = await call_anthropic(
        prompt=prompt,
        system=CREATIVE_ANALYSIS_SYSTEM,
        model=config.creative_analysis_model,
        temperature=0.3,  # Low temp for factual extraction
        config=config,
    )

    extracted = response.parse_json()

    card = CreativeCard(
        creative_id=f"cr_{uuid.uuid4().hex[:12]}",
        brand=upload.brand,
        category=upload.category,
        format=upload.format,
        source_url=upload.image_url,
        extraction_model=response.model,
        **extracted,
    )

    return card, response
