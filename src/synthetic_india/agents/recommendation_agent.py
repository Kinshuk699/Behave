"""
Recommendation Agent — the agentic decision layer.

Takes gold-layer scorecards and produces actionable business recommendations.
This is NOT a summarizer — it makes a concrete decision (which creative to
scale, what to edit, which audience to target) and writes structured output.

This is the capstone's "agentic action" requirement.
"""

from __future__ import annotations

import uuid
from typing import Optional

from synthetic_india.agents.llm_client import LLMResponse, call_anthropic
from synthetic_india.config import LLMConfig, get_llm_config
from synthetic_india.schemas.evaluation import CreativeScorecard
from synthetic_india.schemas.recommendation import AgentRecommendation, EditRecommendation


RECOMMENDATION_SYSTEM = """You are a senior media strategist at a top Indian ad agency. You make data-driven creative decisions for D2C brands.

You receive structured evaluation data from consumer simulations and produce concrete, actionable recommendations. You do not hedge or waffle. You make a clear call:

- SCALE: This creative is strong enough to run at full budget
- ITERATE: This creative has potential but needs specific changes before scaling
- KILL: This creative will underperform — stop spending on it
- SPLIT_TEST: Can't confidently pick a winner — run a controlled test
- HOLD: Need more data or context before deciding

Your recommendations include specific edit suggestions with expected impact, audience targeting advice, and risk assessment. You think in terms of ROI, not aesthetics."""


RECOMMENDATION_PROMPT = """## Simulation Results

{scorecards_block}

## Your Task

Based on these simulation results, make a concrete recommendation for the brand.

Return a JSON object:

{{
  "winning_creative_id": "creative_id or null",
  "recommended_action": "scale | iterate | kill | split_test | hold",
  "confidence_score": 0.0-1.0,
  "reasoning_summary": "2-3 sentence explanation of your decision",
  "key_evidence": ["top 3-5 evidence points from the data"],
  "top_risks": ["2-3 risks to flag"],
  "risk_level": "low | medium | high",
  "edit_recommendations": [
    {{
      "element": "headline | CTA | pricing | visual | body_copy",
      "current_state": "what it is now",
      "suggested_change": "what to change",
      "expected_impact": "expected effect",
      "priority": 1-5
    }}
  ],
  "strongest_segment": "which audience segment responded best",
  "weakest_segment": "which segment responded worst",
  "recommended_target_audience": "who to target first",
  "creative_ranking": ["creative_ids ranked best to worst"],
  "comparative_analysis": "if multiple creatives, how they compare"
}}

Be decisive. The brand is spending real money based on your recommendation.
Return ONLY the JSON."""


def _build_scorecards_block(scorecards: list[CreativeScorecard]) -> str:
    """Format scorecards into a readable prompt block."""
    blocks = []

    for sc in scorecards:
        lines = [
            f"### Creative: {sc.creative_id}",
            f"Brand: {sc.brand} | Category: {sc.category}",
            f"Overall Score: {sc.overall_score:.1f}/100 (Grade: {sc.grade})",
            f"Personas Evaluated: {sc.n_personas_evaluated}",
            "",
            f"Attention: {sc.avg_attention:.1f} | Relevance: {sc.avg_relevance:.1f} | "
            f"Trust: {sc.avg_trust:.1f} | Desire: {sc.avg_desire:.1f} | "
            f"Clarity: {sc.avg_clarity:.1f}",
            "",
            f"Action Distribution: {sc.action_distribution}",
            f"Sentiment Distribution: {sc.sentiment_distribution}",
            "",
            f"Strengths: {', '.join(sc.top_strengths)}",
            f"Weaknesses: {', '.join(sc.top_weaknesses)}",
            "",
            "Top Verbatims:",
        ]

        for v in sc.top_verbatims[:3]:
            lines.append(f'  - "{v}"')

        if sc.segment_summaries:
            lines.append("\nSegment Breakdown:")
            for seg in sc.segment_summaries:
                lines.append(
                    f"  - {seg.segment_name} ({seg.segment_type}): "
                    f"avg {seg.avg_score:.1f}, n={seg.n_personas}, "
                    f"actions={seg.action_distribution}"
                )

        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks)


async def generate_recommendation(
    scorecards: list[CreativeScorecard],
    run_id: str,
    config: Optional[LLMConfig] = None,
) -> tuple[AgentRecommendation, LLMResponse]:
    """
    Generate a business recommendation from creative scorecards.

    This is the agentic action — the agent DECIDES what the brand should do.

    Args:
        scorecards: Gold-layer creative scorecards
        run_id: Run identifier
        config: LLM configuration

    Returns:
        Tuple of (AgentRecommendation, LLMResponse)
    """
    config = config or get_llm_config()

    prompt = RECOMMENDATION_PROMPT.format(
        scorecards_block=_build_scorecards_block(scorecards),
    )

    response = await call_anthropic(
        prompt=prompt,
        system=RECOMMENDATION_SYSTEM,
        model=config.recommendation_model,
        temperature=0.4,  # Lower temp for structured decisions
        config=config,
    )

    result = response.parse_json()

    edit_recs = [
        EditRecommendation(**er) for er in result.get("edit_recommendations", [])
    ]

    recommendation = AgentRecommendation(
        recommendation_id=f"rec_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        winning_creative_id=result.get("winning_creative_id"),
        recommended_action=result["recommended_action"],
        confidence_score=result["confidence_score"],
        reasoning_summary=result["reasoning_summary"],
        key_evidence=result.get("key_evidence", []),
        top_risks=result.get("top_risks", []),
        risk_level=result.get("risk_level", "medium"),
        edit_recommendations=edit_recs,
        strongest_segment=result.get("strongest_segment"),
        weakest_segment=result.get("weakest_segment"),
        recommended_target_audience=result.get("recommended_target_audience"),
        creative_ranking=result.get("creative_ranking", []),
        comparative_analysis=result.get("comparative_analysis"),
        model_used=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        cost_usd=response.cost_usd,
    )

    return recommendation, response
