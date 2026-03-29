"""Creative card models — normalized representation of ad creatives."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreativeFormat(str, Enum):
    STATIC_IMAGE = "static_image"
    CAROUSEL = "carousel"
    VIDEO_THUMBNAIL = "video_thumbnail"
    LANDING_PAGE = "landing_page"
    STORY_AD = "story_ad"
    REEL_AD = "reel_ad"


class VisualStyle(str, Enum):
    MINIMAL = "minimal"
    BOLD_GRAPHIC = "bold_graphic"
    LIFESTYLE = "lifestyle"
    PRODUCT_FOCUSED = "product_focused"
    UGC_STYLE = "ugc_style"
    CELEB_ENDORSEMENT = "celeb_endorsement"
    TRADITIONAL = "traditional"
    MODERN = "modern"


class PriceFraming(str, Enum):
    PREMIUM = "premium"
    VALUE = "value"
    DISCOUNT = "discount"
    COMPARISON = "comparison"
    NO_PRICE = "no_price"


# ── Creative Card ─────────────────────────────────────────────


class CreativeCard(BaseModel):
    """
    Normalized structured representation of a marketing creative.

    This is the single most important schema in the system — it is the
    normalization boundary between raw creative assets and agent evaluation.
    If extraction is lossy here, every downstream judgment degrades.
    """

    creative_id: str = Field(..., description="Unique identifier for the creative")
    brand: str
    category: str
    format: CreativeFormat
    source_url: Optional[str] = None

    # Text extraction
    headline: Optional[str] = Field(None, description="Primary headline / hook text")
    body_copy: Optional[str] = Field(None, description="Supporting body text")
    cta_text: Optional[str] = Field(None, description="Call-to-action text: 'Shop Now', 'Learn More'")
    cta_type: Optional[str] = Field(None, description="buy, learn_more, sign_up, download, etc.")

    # Pricing signals
    price_shown: Optional[float] = None
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    price_framing: PriceFraming = PriceFraming.NO_PRICE

    # Persuasion cues
    urgency_cues: list[str] = Field(
        default_factory=list, description="'Limited time', 'Only 3 left', etc."
    )
    social_proof_cues: list[str] = Field(
        default_factory=list, description="'10K+ reviews', 'As seen on Shark Tank', etc."
    )
    trust_signals: list[str] = Field(
        default_factory=list, description="'Dermatologist tested', 'ISO certified', etc."
    )
    emotional_hooks: list[str] = Field(
        default_factory=list, description="'For your family', 'Be the best version', etc."
    )

    # Visual analysis
    visual_style: Optional[VisualStyle] = None
    color_dominant: Optional[str] = None
    product_visibility: float = Field(
        0.5, ge=0, le=1, description="0 = product hidden, 1 = product hero shot"
    )
    human_presence: bool = False
    celebrity_present: bool = False

    # Language
    language_primary: str = "English"
    language_secondary: Optional[str] = None
    code_mixed: bool = Field(False, description="Uses Hinglish or multi-language mixing")

    # India-specific context
    festival_context: Optional[str] = Field(
        None, description="Festival tie-in if present: Diwali, Holi, Eid, Navratri, etc."
    )
    target_city_tier: Optional[str] = Field(
        None, description="Target city tier: 'Tier 1', 'Tier 2-3', 'Metro', 'Pan-India'"
    )
    cultural_references: list[str] = Field(
        default_factory=list,
        description="Cultural motifs: 'rangoli', 'Bollywood celeb', 'cricket', 'joint family', etc.",
    )

    # Brand context (v2) — extracted by LLM or provided manually
    brand_positioning: Optional[str] = Field(
        None, description="heritage, premium, mass_market, value, disruptor, luxury"
    )
    brand_era: Optional[str] = Field(
        None, description="legacy, established, growth, startup"
    )
    marketing_tone: Optional[str] = Field(
        None, description="aspirational, playful, informational, urgency, nostalgia, edgy"
    )

    # Vision-native (v2) — raw ad image for direct LLM evaluation
    image_path: Optional[str] = Field(
        None, description="Local path to raw ad image; base64-encoded at eval time"
    )

    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_model: Optional[str] = None
    extraction_confidence: float = Field(
        1.0, ge=0, le=1, description="How confident the extraction pipeline is"
    )

    model_config = ConfigDict(use_enum_values=True)


class CreativeUpload(BaseModel):
    """Raw creative upload before extraction — bronze layer record."""

    upload_id: str
    brand: str
    category: str
    format: CreativeFormat
    file_path: Optional[str] = None
    image_url: Optional[str] = None
    raw_text: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    run_id: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)
