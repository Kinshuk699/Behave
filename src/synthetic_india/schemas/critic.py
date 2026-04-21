"""Critic Agent output models — quality gate for persona evaluations."""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


# ── Weights for overall quality computation ──────────────────
# Sycophancy is inverted: high sycophancy_score = BAD, so we flip it.
_WEIGHTS = {
    "persona_consistency": 0.30,
    "sycophancy": 0.25,       # applied to (10 - sycophancy_score)
    "cultural_authenticity": 0.25,
    "action_reasoning_alignment": 0.20,
}

PASS_THRESHOLD = 6.0  # overall_quality must be >= this to pass


class CriticVerdict(BaseModel):
    """Quality verdict for a single PersonaEvaluation."""

    evaluation_id: str
    persona_id: str

    # 4 sub-scores (0-10 each)
    persona_consistency: float = Field(ge=0, le=10)
    sycophancy_score: float = Field(ge=0, le=10)  # 0=genuine, 10=sycophantic
    cultural_authenticity: float = Field(ge=0, le=10)
    action_reasoning_alignment: float = Field(ge=0, le=10)

    explanation: str
    flags: list[str] = Field(default_factory=list)

    # Phase 3 — deterministic pre-critic violations (any entry vetoes pass).
    rule_flags: list[str] = Field(
        default_factory=list,
        description="Deterministic rule violations from critic_rules.py. Non-empty forces passed=False.",
    )

    # Metadata
    model_used: str = ""
    cost_usd: float = 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_quality(self) -> float:
        """Weighted combination of sub-scores. Sycophancy is inverted."""
        score = (
            _WEIGHTS["persona_consistency"] * self.persona_consistency
            + _WEIGHTS["sycophancy"] * (10.0 - self.sycophancy_score)
            + _WEIGHTS["cultural_authenticity"] * self.cultural_authenticity
            + _WEIGHTS["action_reasoning_alignment"] * self.action_reasoning_alignment
        )
        return round(score, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        if self.rule_flags:
            return False
        return self.overall_quality >= PASS_THRESHOLD


class CriticRunSummary(BaseModel):
    """Aggregated critic results across all evaluations in a run."""

    run_id: str
    verdicts: list[CriticVerdict]
    total_evaluated: int
    total_passed: int
    total_failed: int
    pass_rate: float
    avg_persona_consistency: float
    avg_sycophancy_score: float
    avg_cultural_authenticity: float
    avg_action_reasoning_alignment: float
    overall_quality_score: float
    quality_contributions: list[dict]

    @classmethod
    def from_verdicts(cls, run_id: str, verdicts: list[CriticVerdict]) -> CriticRunSummary:
        """Build summary from a list of individual verdicts."""
        n = len(verdicts)
        if n == 0:
            return cls(
                run_id=run_id,
                verdicts=[],
                total_evaluated=0,
                total_passed=0,
                total_failed=0,
                pass_rate=0.0,
                avg_persona_consistency=0.0,
                avg_sycophancy_score=0.0,
                avg_cultural_authenticity=0.0,
                avg_action_reasoning_alignment=0.0,
                overall_quality_score=0.0,
                quality_contributions=[],
            )

        passed = [v for v in verdicts if v.passed]
        overall_sum = sum(v.overall_quality for v in verdicts)

        contributions = []
        for v in verdicts:
            weight = v.overall_quality / overall_sum if overall_sum > 0 else 1.0 / n
            contributions.append({
                "persona_id": v.persona_id,
                "evaluation_id": v.evaluation_id,
                "overall_quality": v.overall_quality,
                "weight": round(weight, 4),
                "contribution": round(v.overall_quality * weight, 4),
                "passed": v.passed,
            })

        return cls(
            run_id=run_id,
            verdicts=verdicts,
            total_evaluated=n,
            total_passed=len(passed),
            total_failed=n - len(passed),
            pass_rate=round(len(passed) / n, 4),
            avg_persona_consistency=round(sum(v.persona_consistency for v in verdicts) / n, 2),
            avg_sycophancy_score=round(sum(v.sycophancy_score for v in verdicts) / n, 2),
            avg_cultural_authenticity=round(sum(v.cultural_authenticity for v in verdicts) / n, 2),
            avg_action_reasoning_alignment=round(sum(v.action_reasoning_alignment for v in verdicts) / n, 2),
            overall_quality_score=round(overall_sum / n, 2),
            quality_contributions=contributions,
        )
