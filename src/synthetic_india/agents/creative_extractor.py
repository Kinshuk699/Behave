"""
Creative Extractor Agent — LLM pre-pass to extract CreativeCard fields from image + brand.

Given just a brand name and an ad image, uses Claude Sonnet to extract:
- Category (constrained to B2C_CATEGORIES vocabulary)
- Headline, body copy, CTA
- Visual style, pricing signals, persuasion cues
- Brand positioning, brand era, marketing tone
- India-specific context (festival, city tier, cultural references)

This eliminates the need for users to manually fill in form fields.
"""

from __future__ import annotations

import json
from typing import Optional

from synthetic_india.agents.image_utils import encode_image
from synthetic_india.agents.llm_client import LLMResponse, call_anthropic
from synthetic_india.categories import B2C_CATEGORIES, BrandPositioning, BrandEra, MarketingTone
from synthetic_india.config import LLMConfig, get_llm_config
from synthetic_india.schemas.creative import CreativeCard, CreativeFormat


# Build category list string for prompt injection
_CATEGORY_LIST = ", ".join(B2C_CATEGORIES)
_POSITIONING_LIST = ", ".join(v.value for v in BrandPositioning)
_ERA_LIST = ", ".join(v.value for v in BrandEra)
_TONE_LIST = ", ".join(v.value for v in MarketingTone)

EXTRACTION_SYSTEM = """You are an expert Indian advertising analyst. You analyze ad creatives — images, text, visual style — and extract structured metadata. You understand the Indian market deeply: brands, categories, regional nuances, Hinglish, festival marketing, and city-tier targeting."""

EXTRACTION_PROMPT = f"""Analyze this ad creative and extract structured metadata.

The brand is: **{{brand}}**

## Category (PICK EXACTLY ONE from this list)
{_CATEGORY_LIST}

IMPORTANT: Pick the category that describes the BRAND's primary industry, not the specific product in this ad. Example: Zepto promoting chocolates for Valentine's → category is "quick_commerce" because Zepto IS a quick commerce platform.

## Brand Context
Assess how this brand positions itself:
- brand_positioning: {_POSITIONING_LIST}
- brand_era: {_ERA_LIST}
- marketing_tone (of THIS specific ad): {_TONE_LIST}

## Extract from the image

Return a JSON object with these fields:

{{{{
  "category": "one of the categories listed above",
  "headline": "primary headline text visible in the ad (or null)",
  "body_copy": "supporting text (or null)",
  "cta_text": "call-to-action text like 'Shop Now', 'Download App' (or null)",
  "cta_type": "buy | learn_more | sign_up | download | visit | null",
  "price_shown": null or number,
  "original_price": null or number,
  "discount_percentage": null or number,
  "price_framing": "premium | value | discount | comparison | no_price",
  "urgency_cues": ["list of urgency triggers"],
  "social_proof_cues": ["list of social proof elements"],
  "trust_signals": ["list of trust elements"],
  "emotional_hooks": ["list of emotional appeals"],
  "visual_style": "minimal | bold_graphic | lifestyle | product_focused | ugc_style | celeb_endorsement | traditional | modern",
  "color_dominant": "primary color in the ad",
  "product_visibility": 0.0 to 1.0,
  "human_presence": true/false,
  "celebrity_present": true/false,
  "language_primary": "English | Hindi | Hinglish | Tamil | etc.",
  "language_secondary": "or null",
  "code_mixed": true/false,
  "festival_context": "Diwali | Holi | Eid | etc. or null",
  "target_city_tier": "Metro | Tier 1 | Tier 2-3 | Pan-India | null",
  "cultural_references": ["any cultural elements visible"],
  "brand_positioning": "{_POSITIONING_LIST}",
  "brand_era": "{_ERA_LIST}",
  "marketing_tone": "{_TONE_LIST}"
}}}}

Return ONLY the JSON. Be precise."""


async def extract_creative_from_image(
    brand: str,
    image_path: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: str = "image/jpeg",
    config: Optional[LLMConfig] = None,
) -> tuple[CreativeCard, LLMResponse]:
    """Extract a full CreativeCard from brand name + ad image.

    Args:
        brand: Brand name (e.g., "Zepto", "Urban Company")
        image_path: Local path to ad image file
        image_base64: Pre-encoded base64 image data
        image_media_type: MIME type of the image
        config: LLM configuration

    Returns:
        Tuple of (CreativeCard, LLMResponse)
    """
    config = config or get_llm_config()

    prompt = EXTRACTION_PROMPT.format(brand=brand)

    # Build vision kwargs
    vision_kwargs: dict = {}
    if image_path:
        b64, media = encode_image(image_path)
        vision_kwargs = {"image_base64": b64, "image_media_type": media}
    elif image_base64:
        vision_kwargs = {"image_base64": image_base64, "image_media_type": image_media_type}

    response = await call_anthropic(
        prompt=prompt,
        system=EXTRACTION_SYSTEM,
        model=config.creative_analysis_model,
        temperature=0.3,  # Low temp for structured extraction
        config=config,
        **vision_kwargs,
    )

    result = response.parse_json()

    # Normalize category to canonical vocabulary
    from synthetic_india.categories import normalize_category
    category = normalize_category(result.get("category", "other"))

    import hashlib
    creative_id = f"live_{hashlib.md5(brand.encode()).hexdigest()[:8]}"

    card = CreativeCard(
        creative_id=creative_id,
        brand=brand,
        category=category,
        format=CreativeFormat.STATIC_IMAGE,
        headline=result.get("headline"),
        body_copy=result.get("body_copy"),
        cta_text=result.get("cta_text"),
        cta_type=result.get("cta_type"),
        price_shown=result.get("price_shown"),
        original_price=result.get("original_price"),
        discount_percentage=result.get("discount_percentage"),
        price_framing=result.get("price_framing", "no_price"),
        urgency_cues=result.get("urgency_cues", []),
        social_proof_cues=result.get("social_proof_cues", []),
        trust_signals=result.get("trust_signals", []),
        emotional_hooks=result.get("emotional_hooks", []),
        visual_style=result.get("visual_style"),
        color_dominant=result.get("color_dominant"),
        product_visibility=result.get("product_visibility", 0.5),
        human_presence=result.get("human_presence", False),
        celebrity_present=result.get("celebrity_present", False),
        language_primary=result.get("language_primary", "English"),
        language_secondary=result.get("language_secondary"),
        code_mixed=result.get("code_mixed", False),
        festival_context=result.get("festival_context"),
        target_city_tier=result.get("target_city_tier"),
        cultural_references=result.get("cultural_references", []),
        brand_positioning=result.get("brand_positioning"),
        brand_era=result.get("brand_era"),
        marketing_tone=result.get("marketing_tone"),
        image_path=image_path,
        extraction_model=response.model,
        extraction_confidence=0.9,
    )

    return card, response
