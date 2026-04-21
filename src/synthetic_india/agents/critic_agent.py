"""
Critic Agent — quality gate for persona evaluations.

Evaluates each PersonaEvaluation against 4 dimensions:
1. Persona consistency — does the evaluation match the persona profile?
2. Sycophancy detection — is the evaluation unrealistically positive?
3. Cultural authenticity — does verbatim/reasoning sound genuinely Indian?
4. Action-reasoning alignment — does primary_action follow from reasoning + scores?

Called inline after each evaluate_creative() call.
If FAIL → quarantine the evaluation, exclude from scorecard aggregation.
"""

from __future__ import annotations

from synthetic_india.agents.llm_client import call_anthropic
from synthetic_india.agents.critic_rules import (
    run_pre_critic_checks,
    run_specificity_check,
)
from synthetic_india.config import LLMConfig, get_llm_config
from synthetic_india.schemas.critic import CriticVerdict, CriticRunSummary
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.persona import PersonaProfile


# ── Prompt Templates ──────────────────────────────────────────

CRITIC_SYSTEM = """\
You are a rigorous quality-assurance critic for synthetic consumer research.

Your job is to evaluate whether a simulated persona's reaction to an advertisement \
is authentic, consistent, and free of common LLM failure modes.

You are NOT judging the ad. You are judging whether the SIMULATED PERSONA'S RESPONSE \
is realistic and faithful to who that person is.

Be harsh. Flag anything that looks generic, sycophantic, or inconsistent. \
Indian consumers are diverse — a skeptic from Mumbai reacts very differently from an \
aspirational buyer in Lucknow.

Respond ONLY with a JSON object (no markdown fences, no preamble)."""


def _build_critic_prompt(persona: PersonaProfile, evaluation: PersonaEvaluation) -> str:
    """Build the user-facing prompt for the critic, embedding persona + evaluation data."""

    # ── Deep persona context (conditional) ───────────────────
    deep_context = ""

    if persona.backstory:
        deep_context += f"\n- backstory: {persona.backstory}"
    if persona.current_life_context:
        deep_context += f"\n- current_life_context: {persona.current_life_context}"

    if persona.generational_touchstones:
        gt = persona.generational_touchstones
        deep_context += f"\n- formative_era: {gt.formative_era}"
        if gt.iconic_ads:
            deep_context += f"\n- iconic_ads: {', '.join(gt.iconic_ads[:3])}"
        deep_context += f"\n- nostalgia_intensity: {gt.nostalgia_intensity}"

    if persona.internal_conflicts:
        conflicts = "; ".join(ic.tension for ic in persona.internal_conflicts[:3])
        deep_context += f"\n- internal_conflicts: {conflicts}"

    if persona.values_hierarchy:
        deep_context += f"\n- values_hierarchy: {', '.join(persona.values_hierarchy)}"

    if persona.cognitive_biases:
        deep_context += f"\n- cognitive_biases: {', '.join(persona.cognitive_biases)}"

    return f"""## Persona Profile

- persona_id: {persona.persona_id}
- archetype: {persona.archetype}
- name: {persona.name}
- tagline: {persona.tagline}
- age: {persona.demographics.age}, gender: {persona.demographics.gender}
- city: {persona.demographics.city} ({persona.demographics.city_tier})
- income: {persona.demographics.income_segment}
- price_sensitivity: {persona.purchase_psychology.price_sensitivity}
- brand_loyalty: {persona.purchase_psychology.brand_loyalty}
- impulse_tendency: {persona.purchase_psychology.impulse_tendency}
- social_proof_need: {persona.purchase_psychology.social_proof_need}
- research_depth: {persona.purchase_psychology.research_depth}
- risk_tolerance: {persona.purchase_psychology.risk_tolerance}
- decision_speed: {persona.purchase_psychology.decision_speed}
- deal_sensitivity: {persona.purchase_psychology.deal_sensitivity}
- trust_signals: {', '.join(persona.emotional_profile.trust_signals)}
- rejection_triggers: {', '.join(persona.emotional_profile.rejection_triggers)}
- inner_monologue_style: {persona.inner_monologue_style}{deep_context}

## Evaluation Being Critiqued

- evaluation_id: {evaluation.evaluation_id}
- primary_action: {evaluation.primary_action}
- secondary_action: {evaluation.secondary_action}
- sentiment: {evaluation.sentiment}
- overall_score: {evaluation.overall_score}/100

### Dimensional Scores (0-10)
- attention: {evaluation.attention_score}
- relevance: {evaluation.relevance_score}
- trust: {evaluation.trust_score}
- desire: {evaluation.desire_score}
- clarity: {evaluation.clarity_score}

### Qualitative
- first_impression: {evaluation.first_impression}
- reasoning: {evaluation.reasoning}
- objections: {evaluation.objections}
- what_would_change_mind: {evaluation.what_would_change_mind}
- verbatim_reaction: {evaluation.verbatim_reaction}
- key_themes: {evaluation.key_themes}
- brand: {evaluation.brand}
- category: {evaluation.category}

## Your Task

Score this evaluation on 4 dimensions (each 0-10):

1. **persona_consistency** (0-10): Does this evaluation match the persona profile above?
   - A skeptic giving all 8+ scores with no objections → low score
   - A researcher with shallow reasoning → low score
   - Match price_sensitivity, brand_loyalty, impulse_tendency to the action and scores
   - Check generational consistency: a 23-year-old should not reference 90s Doordarshan ads unless their persona explicitly lists them in iconic_ads. Flag age-inappropriate cultural references.
   - Verify internal conflicts are reflected — a persona torn about spending should not give enthusiastic purchase_intent without acknowledging that tension

2. **sycophancy_score** (0-10, where 0=genuine and 10=sycophantic):
   - Unrealistically positive sentiment + high scores + no real objections → high
   - Generic praise without specific product/brand references → high
   - Authentic negative or mixed reactions → low (good)

3. **cultural_authenticity** (0-10, where 0=generic/Western and 10=authentically Indian):
   - Does the verbatim sound like a real person from {persona.demographics.city}?
   - Are references culturally grounded (not generic American consumer speak)?
   - Language mixing (Hinglish, regional phrases) where appropriate?

4. **action_reasoning_alignment** (0-10):
   - Does the primary_action logically follow from the reasoning and dimensional scores?
   - Low trust_score (3/10) but primary_action is "purchase_intent" → low alignment
   - High desire but many objections and action is "read" → reasonable alignment

Respond with this exact JSON structure:
{{
    "persona_consistency": <float 0-10>,
    "sycophancy_score": <float 0-10>,
    "cultural_authenticity": <float 0-10>,
    "action_reasoning_alignment": <float 0-10>,
    "explanation": "<2-3 sentence explanation of your verdict>",
    "flags": ["<issue1>", "<issue2>"]
}}"""


def build_critic_prompt(
    persona: PersonaProfile,
    evaluation: PersonaEvaluation,
) -> tuple[str, str]:
    """Public interface — returns (system_prompt, user_prompt) for testing."""
    return CRITIC_SYSTEM, _build_critic_prompt(persona, evaluation)


async def evaluate_single(
    persona: PersonaProfile,
    evaluation: PersonaEvaluation,
    config: LLMConfig | None = None,
) -> CriticVerdict:
    """Run the critic on a single persona evaluation. Makes one LLM call."""
    config = config or get_llm_config()
    system, prompt = build_critic_prompt(persona, evaluation)

    response = await call_anthropic(
        prompt=prompt,
        system=system,
        model=config.critic_model,
        max_tokens=1024,
        temperature=0.3,  # low temp for consistent judgments
        config=config,
    )

    parsed = response.parse_json()

    rule_flags = run_pre_critic_checks(persona, evaluation) + run_specificity_check(
        evaluation
    )

    return CriticVerdict(
        evaluation_id=evaluation.evaluation_id,
        persona_id=evaluation.persona_id,
        persona_consistency=parsed["persona_consistency"],
        sycophancy_score=parsed["sycophancy_score"],
        cultural_authenticity=parsed["cultural_authenticity"],
        action_reasoning_alignment=parsed["action_reasoning_alignment"],
        explanation=parsed["explanation"],
        flags=parsed.get("flags", []),
        rule_flags=rule_flags,
        model_used=response.model,
        cost_usd=response.cost_usd,
    )


def summarize_run(run_id: str, verdicts: list[CriticVerdict]) -> CriticRunSummary:
    """Pure Python rollup — no LLM call. Aggregates individual verdicts."""
    return CriticRunSummary.from_verdicts(run_id=run_id, verdicts=verdicts)
