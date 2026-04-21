"""
Phase 3.5 — Cross-model critic: GPT-4o-mini second opinion on Claude verdicts.

Opus pressure-test issue addressed:
  #4 — same-model bias. Claude critic on Claude evaluator misses failure
       modes both share. A second model from a different family
       (OpenAI GPT-4o-mini) catches Claude's blind spots.

Design:
  1. Run the existing critic prompt through GPT-4o-mini in parallel with
     the Claude critic call.
  2. Compute per-dimension disagreement (absolute differences).
  3. If any dim diff exceeds `threshold` OR the two verdicts disagree on
     pass/fail, emit a `cross_model_disagreement_*` flag.
  4. Flags merge into `CriticVerdict.rule_flags` (Phase 3 already
     guarantees rule_flags vetoes passed).
"""

from __future__ import annotations

from synthetic_india.agents.llm_client import call_openai
from synthetic_india.config import LLMConfig, get_llm_config
from synthetic_india.schemas.critic import CriticVerdict
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.persona import PersonaProfile


_DIMS: tuple[str, ...] = (
    "persona_consistency",
    "sycophancy_score",
    "cultural_authenticity",
    "action_reasoning_alignment",
)

DEFAULT_DISAGREEMENT_THRESHOLD = 3.0


def compute_disagreement(a: CriticVerdict, b: CriticVerdict) -> dict:
    """Pure function — per-dim absolute diffs, max diff, and pass/fail mismatch."""
    per_dim: dict[str, float] = {}
    for dim in _DIMS:
        diff = abs(getattr(a, dim) - getattr(b, dim))
        per_dim[dim] = round(diff, 4)
    max_abs_diff = max(per_dim.values()) if per_dim else 0.0
    return {
        "per_dim": per_dim,
        "max_abs_diff": round(max_abs_diff, 4),
        "verdicts_disagree": a.passed != b.passed,
    }


def cross_model_flags(
    primary: CriticVerdict,
    secondary: CriticVerdict,
    threshold: float = DEFAULT_DISAGREEMENT_THRESHOLD,
) -> list[str]:
    """Emit rule_flag-style strings when models disagree."""
    flags: list[str] = []
    diag = compute_disagreement(primary, secondary)

    over_threshold = [
        (dim, diff) for dim, diff in diag["per_dim"].items() if diff > threshold
    ]
    for dim, diff in over_threshold:
        flags.append(
            f"cross_model_disagreement_{dim}_diff_{diff:.1f}"
        )

    if diag["verdicts_disagree"]:
        flags.append(
            f"cross_model_verdict_mismatch: claude_passed={primary.passed} "
            f"openai_passed={secondary.passed}"
        )

    return flags


# ── Async orchestrator: call GPT critic + return verdict ────


async def call_openai_critic(
    persona: PersonaProfile,
    evaluation: PersonaEvaluation,
    config: LLMConfig | None = None,
    model: str = "gpt-4o-mini",
) -> CriticVerdict:
    """Run the same critic prompt through GPT-4o-mini and parse into a CriticVerdict.

    Imports `build_critic_prompt` lazily to avoid a circular import with
    `critic_agent.py`.
    """
    from synthetic_india.agents.critic_agent import build_critic_prompt

    config = config or get_llm_config()
    system, prompt = build_critic_prompt(persona=persona, evaluation=evaluation)

    response = await call_openai(
        prompt=prompt,
        system=system,
        model=model,
        max_tokens=1024,
        temperature=0.3,
        config=config,
    )
    parsed = response.parse_json()

    return CriticVerdict(
        evaluation_id=evaluation.evaluation_id,
        persona_id=evaluation.persona_id,
        persona_consistency=parsed["persona_consistency"],
        sycophancy_score=parsed["sycophancy_score"],
        cultural_authenticity=parsed["cultural_authenticity"],
        action_reasoning_alignment=parsed["action_reasoning_alignment"],
        explanation=parsed["explanation"],
        flags=parsed.get("flags", []),
        model_used=response.model,
        cost_usd=response.cost_usd,
    )
