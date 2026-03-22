"""Evaluation output models — what a persona produces after seeing a creative."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ConsumerAction(str, Enum):
    """The primary action a persona would take upon seeing the creative."""
    SCROLL_PAST = "scroll_past"
    PAUSE = "pause"
    READ = "read"
    ENGAGE = "engage"
    CLICK = "click"
    SAVE = "save"
    SHARE = "share"
    PURCHASE_INTENT = "purchase_intent"
    NEGATIVE_REACT = "negative_react"


class Sentiment(str, Enum):
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


# ── Individual Persona Evaluation ─────────────────────────────


class PersonaEvaluation(BaseModel):
    """
    Structured output from one persona evaluating one creative.
    This is the atomic unit of the simulation.
    """

    evaluation_id: str
    run_id: str
    creative_id: str
    persona_id: str

    # Core reaction
    primary_action: ConsumerAction
    secondary_action: Optional[ConsumerAction] = None
    sentiment: Sentiment
    overall_score: float = Field(..., ge=0, le=100, description="0-100 appeal score")

    # Dimensional scores
    attention_score: float = Field(..., ge=0, le=10, description="Would this stop their scroll?")
    relevance_score: float = Field(..., ge=0, le=10, description="Is this relevant to their life?")
    trust_score: float = Field(..., ge=0, le=10, description="Do they trust this ad?")
    desire_score: float = Field(..., ge=0, le=10, description="Do they want the product?")
    clarity_score: float = Field(..., ge=0, le=10, description="Is the message clear?")

    # Qualitative output
    first_impression: str = Field(
        ..., description="What the persona notices/thinks in the first 2 seconds"
    )
    reasoning: str = Field(
        ..., description="Why they would take their primary action — in their voice"
    )
    objections: list[str] = Field(
        default_factory=list, description="What concerns or pushback they have"
    )
    what_would_change_mind: Optional[str] = Field(
        None, description="What would make them act differently"
    )
    verbatim_reaction: str = Field(
        ..., description="A realistic quote in the persona's natural speaking style"
    )

    # Memory-relevant metadata
    importance_score: float = Field(
        ..., ge=0, le=10,
        description="How poignant/memorable this experience is for the persona (for memory retrieval)"
    )
    category: str = Field(..., description="Product category for memory indexing")
    brand: str = Field(..., description="Brand name for memory indexing")
    key_themes: list[str] = Field(
        default_factory=list, description="Themes noticed: price, trust, aspiration, fear, etc."
    )

    # Execution metadata
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)

    # Memory context (filled if memory was used)
    memories_retrieved: int = 0
    memory_context_used: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


# ── Aggregated Outputs ────────────────────────────────────────


class SegmentSummary(BaseModel):
    """Aggregated evaluation across a segment (archetype, demographic slice, etc.)."""

    run_id: str
    creative_id: str
    segment_name: str
    segment_type: str  # archetype, age_group, city_tier, income, etc.

    n_personas: int
    avg_score: float
    action_distribution: dict[str, int]  # action -> count
    sentiment_distribution: dict[str, int]
    avg_attention: float
    avg_relevance: float
    avg_trust: float
    avg_desire: float
    avg_clarity: float
    top_objections: list[str]
    top_themes: list[str]
    representative_verbatim: str


class CreativeScorecard(BaseModel):
    """Top-level scorecard for a creative across all personas in a run."""

    run_id: str
    creative_id: str
    brand: str
    category: str

    n_personas_evaluated: int
    overall_score: float
    grade: str  # A, B, C, D, F

    action_distribution: dict[str, int]
    sentiment_distribution: dict[str, int]
    avg_attention: float
    avg_relevance: float
    avg_trust: float
    avg_desire: float
    avg_clarity: float

    top_strengths: list[str]
    top_weaknesses: list[str]
    top_verbatims: list[str]

    segment_summaries: list[SegmentSummary] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
