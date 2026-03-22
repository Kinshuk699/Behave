"""Recommendation models — the agentic decision layer output."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EditRecommendation(BaseModel):
    """A specific creative edit recommendation."""
    element: str  # headline, CTA, pricing, visual, body_copy
    current_state: str
    suggested_change: str
    expected_impact: str
    priority: int = Field(..., ge=1, le=5, description="1 = highest priority")


class AgentRecommendation(BaseModel):
    """
    The agent's final business recommendation for a simulation run.
    This is the 'agentic action' that satisfies the capstone requirement.
    """

    recommendation_id: str
    run_id: str

    # Core decision
    winning_creative_id: Optional[str] = Field(
        None, description="Which creative to scale — null if none recommended"
    )
    recommended_action: str = Field(
        ..., description="scale, iterate, kill, split_test, or hold"
    )
    confidence_score: float = Field(..., ge=0, le=1, description="Agent's confidence in the rec")

    # Reasoning
    reasoning_summary: str = Field(..., description="Why the agent chose this action")
    key_evidence: list[str] = Field(
        default_factory=list, description="Top evidence points driving the decision"
    )

    # Risk assessment
    top_risks: list[str] = Field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high

    # Edit suggestions
    edit_recommendations: list[EditRecommendation] = Field(default_factory=list)

    # Audience targeting
    strongest_segment: Optional[str] = None
    weakest_segment: Optional[str] = None
    recommended_target_audience: Optional[str] = None

    # Comparison (if multiple creatives)
    creative_ranking: list[str] = Field(
        default_factory=list, description="Creative IDs ranked best to worst"
    )
    comparative_analysis: Optional[str] = None

    # Execution metadata
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RunMetadata(BaseModel):
    """Metadata for a complete simulation run."""

    run_id: str
    brand: str
    category: str
    creative_ids: list[str]
    persona_ids: list[str]

    cohort_size: int
    total_evaluations: int
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Quality metrics
    quarantined_records: int = 0
    successful_evaluations: int = 0
    failed_evaluations: int = 0
