"""Persona data models — the 'Soul' layer of each synthetic consumer."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from synthetic_india.schemas.memory import SceneMemory


class Archetype(str, Enum):
    RESEARCHER = "researcher"
    IMPULSE_BUYER = "impulse_buyer"
    PRICE_ANCHOR = "price_anchor"
    BRAND_LOYALIST = "brand_loyalist"
    TREND_FOLLOWER = "trend_follower"
    SKEPTIC = "skeptic"
    PRAGMATIST = "pragmatist"
    ASPIRATIONAL_BUYER = "aspirational_buyer"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"


class CityTier(str, Enum):
    METRO = "metro"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    RURAL = "rural"


class IncomeSegment(str, Enum):
    BUDGET = "budget"
    LOWER_MIDDLE = "lower_middle"
    MIDDLE = "middle"
    UPPER_MIDDLE = "upper_middle"
    PREMIUM = "premium"
    LUXURY = "luxury"


# ── Demographics ──────────────────────────────────────────────


class Demographics(BaseModel):
    age: int = Field(..., ge=16, le=80)
    gender: Gender
    city: str
    city_tier: CityTier
    state: str
    income_segment: IncomeSegment
    language_primary: str = "Hindi"
    language_secondary: Optional[str] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    family_status: Optional[str] = None


# ── Behavioral Profile ────────────────────────────────────────


class PurchasePsychology(BaseModel):
    """How this persona makes buying decisions."""
    price_sensitivity: float = Field(..., ge=0, le=1, description="0 = price-insensitive, 1 = extreme haggler")
    brand_loyalty: float = Field(..., ge=0, le=1, description="0 = brand-agnostic, 1 = ride-or-die loyalist")
    impulse_tendency: float = Field(..., ge=0, le=1, description="0 = always deliberate, 1 = instant buyer")
    social_proof_need: float = Field(..., ge=0, le=1, description="0 = independent decider, 1 = needs validation")
    research_depth: float = Field(..., ge=0, le=1, description="0 = gut feel, 1 = reads every review")
    risk_tolerance: float = Field(..., ge=0, le=1, description="0 = plays it safe, 1 = tries everything new")
    decision_speed: str = Field(..., description="slow | moderate | fast | impulsive")
    deal_sensitivity: float = Field(..., ge=0, le=1, description="0 = ignores deals, 1 = only buys on discount")


class MediaBehavior(BaseModel):
    """How this persona consumes media and ads."""
    platform_primary: str = Field(..., description="Instagram, YouTube, WhatsApp, etc.")
    platform_secondary: Optional[str] = None
    ad_tolerance: float = Field(..., ge=0, le=1, description="0 = blocks everything, 1 = reads every ad")
    scroll_speed: str = Field(..., description="slow | moderate | fast")
    video_preference: float = Field(..., ge=0, le=1, description="0 = text/image only, 1 = video-first")
    influencer_trust: float = Field(..., ge=0, le=1, description="0 = distrusts all, 1 = buys what influencers say")
    content_language_preference: str = "Hindi"


class EmotionalProfile(BaseModel):
    """Emotional triggers and sensitivities."""
    aspiration_drivers: list[str] = Field(
        ..., description="What they aspire to: status, health, family, modernity, etc."
    )
    trust_signals: list[str] = Field(
        ..., description="What builds trust: certifications, reviews, heritage, celeb endorsement"
    )
    rejection_triggers: list[str] = Field(
        ..., description="What causes instant rejection: western-washing, high price, poor Hindi"
    )
    emotional_hooks: list[str] = Field(
        ..., description="What emotionally engages: nostalgia, FOMO, family, pride, value"
    )


class CategoryAffinity(BaseModel):
    """Interest and spend pattern for a product category."""
    category: str
    interest_level: float = Field(..., ge=0, le=1)
    monthly_spend_inr: Optional[float] = None
    preferred_brands: list[str] = Field(default_factory=list)
    purchase_frequency: Optional[str] = None  # weekly, monthly, quarterly, rarely
    brand_relationships: list["BrandRelationship"] = Field(default_factory=list)


# ── Deep Persona Models (2026-03-28) ─────────────────────────


class GenerationalTouchstones(BaseModel):
    """Cultural memory that shapes purchasing instincts."""
    formative_era: str = Field(..., description="e.g. '90s Doordarshan kid', 'post-Jio digital native'")
    iconic_ads: list[str] = Field(default_factory=list, description="Ads burned into memory")
    cultural_references: list[str] = Field(default_factory=list, description="Events, shows, movements")
    nostalgia_intensity: float = Field(..., ge=0, le=1, description="0 = forward-looking, 1 = deeply nostalgic")
    formative_brands: list[str] = Field(default_factory=list, description="Brands from childhood/teen years")


class InternalConflict(BaseModel):
    """A tension the persona lives with when making purchase decisions."""
    tension: str = Field(..., description="The push-pull, e.g. 'Wants premium but EMI eats budget'")
    resolution_tendency: str = Field(..., description="How they usually resolve it")


class BrandRelationship(BaseModel):
    """Emotional relationship with a specific brand — beyond 'preferred'."""
    brand: str
    relationship_type: str = Field(..., description="loyal_lover, nostalgic_friend, burned_ex, curious_flirt, etc.")
    emotional_history: str = Field(..., description="Why this relationship exists")
    intensity: float = Field(..., ge=0, le=1, description="0 = indifferent, 1 = identity-defining")


class Influencer(BaseModel):
    """A person or group that shapes this persona's purchase decisions."""
    role: str = Field(..., description="mother, spouse, college_friends, YouTube_reviewer, etc.")
    influence_strength: float = Field(..., ge=0, le=1, description="0 = ignored, 1 = decisive")
    influence_domain: str = Field(..., description="What categories they influence, e.g. 'grocery, household'")


# ── Phase 4: Persona contradictions (Opus #5) ────────────────

# Whitelist of psychology dials that BehaviorModifier may shift.
_VALID_DIALS: frozenset[str] = frozenset(
    {
        "price_sensitivity",
        "brand_loyalty",
        "impulse_tendency",
        "social_proof_need",
        "research_depth",
        "risk_tolerance",
        "deal_sensitivity",
    }
)


class ValueConflict(BaseModel):
    """Two competing values the persona holds, with the contexts that activate each.

    Richer than free-text `internal_conflicts` because it forces structure:
    'value_a vs value_b, triggered by context_a vs context_b'.
    """

    value_a: str = Field(..., description="e.g. 'thrift', 'family_security'")
    value_b: str = Field(..., description="e.g. 'status', 'self_reward'")
    context_a: str = Field(
        ..., description="Situation where value_a wins (e.g. 'grocery shopping with mother')"
    )
    context_b: str = Field(
        ..., description="Situation where value_b wins (e.g. 'dinner with college friends')"
    )
    dominant_side: Literal["a", "b", "situational"] = Field(
        "situational",
        description="Which side usually wins overall: 'a', 'b', or 'situational' (depends).",
    )


class BehaviorModifier(BaseModel):
    """Named situation that nudges psychology dials at decision time.

    e.g. {'end_of_month': BehaviorModifier(description='bills cleared, salary not in',
          dial_deltas={'price_sensitivity': +0.2, 'impulse_tendency': -0.15})}
    """

    description: str = Field(..., description="Human-readable trigger context.")
    dial_deltas: dict[str, float] = Field(
        ...,
        description="Map of psychology dial name → signed delta in [-1, 1].",
    )

    @field_validator("dial_deltas")
    @classmethod
    def _validate_dials(cls, v: dict[str, float]) -> dict[str, float]:
        for dial, delta in v.items():
            if dial not in _VALID_DIALS:
                raise ValueError(
                    f"unknown dial '{dial}'; must be one of {sorted(_VALID_DIALS)}"
                )
            if not -1.0 <= delta <= 1.0:
                raise ValueError(
                    f"delta for '{dial}' = {delta} out of range [-1.0, 1.0]"
                )
        return v


# ── Full Persona ──────────────────────────────────────────────


class PersonaProfile(BaseModel):
    """Complete synthetic consumer persona — the Soul of the agent."""

    persona_id: str = Field(..., description="Unique identifier, e.g. 'researcher_delhi_01'")
    name: str = Field(..., description="Human-readable name for the persona")
    archetype: Archetype
    tagline: str = Field(..., description="One-line behavioral summary")

    demographics: Demographics
    purchase_psychology: PurchasePsychology
    media_behavior: MediaBehavior
    emotional_profile: EmotionalProfile
    category_affinities: list[CategoryAffinity] = Field(default_factory=list)

    backstory: str = Field(
        ..., description="2-3 sentence narrative grounding: who they are, what shapes their choices"
    )
    current_life_context: str = Field(
        ..., description="What is happening in their life right now that might affect decisions"
    )
    inner_monologue_style: str = Field(
        ..., description="How they think/talk to themselves when evaluating a product"
    )

    # ── Deep persona fields (2026-03-28) ──
    generational_touchstones: Optional[GenerationalTouchstones] = None
    internal_conflicts: list[InternalConflict] = Field(default_factory=list)
    influence_network: list[Influencer] = Field(default_factory=list)
    values_hierarchy: list[str] = Field(default_factory=list, description="Ordered: most important first")
    cognitive_biases: list[str] = Field(default_factory=list, description="e.g. present_bias, anchoring, bandwagon")

    # ── Nostalgia / Scene Memory (Manufacturing Nostalgia addendum, 2026-04-08) ──
    # Formative-era scene-memories that ground the persona in lived experience.
    # Seeded at initialization; retrieved preferentially via high emotional_arousal.
    formative_window: Optional[list[int]] = Field(
        None,
        description=(
            "Year range [start_year, end_year] of the persona's reminiscence bump "
            "(approx ages 10–22). Determines which cultural references trigger genuine nostalgia."
        )
    )
    scene_memories: list[SceneMemory] = Field(
        default_factory=list,
        description=(
            "5–7 formative-era scene-memories. Each contains sensory anchor, life context, "
            "and present contrast. Loaded into MemoryStream at initialization with high "
            "emotional_arousal so they surface during evaluation."
        )
    )

    # ── Phase 4 (Opus #5): Persona contradictions ──
    shadow_archetype: Optional[Archetype] = Field(
        None,
        description=(
            "The archetype this persona becomes when stressed, excited, or off-script. "
            "e.g. a 'pragmatist' whose shadow is 'impulse_buyer' — captures the moments "
            "when normal rules don't apply."
        ),
    )
    value_conflicts: list[ValueConflict] = Field(
        default_factory=list,
        description=(
            "Pairs of competing values with the contexts that activate each side. "
            "Richer than free-text internal_conflicts because each side has an explicit trigger."
        ),
    )
    context_modifiers: dict[str, BehaviorModifier] = Field(
        default_factory=dict,
        description=(
            "Named situations (e.g. 'end_of_month', 'salary_day', 'after_argument_with_spouse') "
            "that shift psychology dials at decision time."
        ),
    )

    model_config = ConfigDict(use_enum_values=True)
