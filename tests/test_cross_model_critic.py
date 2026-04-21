"""
Phase 3.5 — Cross-model critic.

Opus pressure-test issue addressed:
  #4 — same-model bias: Claude critic judging Claude evaluator misses
       failure modes both share.

Design: run the same critic prompt through a second model (GPT-4o-mini)
and compare the two CriticVerdicts. Significant disagreement on any
sub-score, or opposite pass/fail verdicts, becomes a rule_flag entry —
which (per Phase 3) forces passed=False.

Public API:
  compute_disagreement(verdict_a, verdict_b) -> dict
      {"max_abs_diff": float, "per_dim": {dim: float}, "verdicts_disagree": bool}

  cross_model_flags(primary, secondary, threshold=3.0) -> list[str]
      Returns flag list (empty if models agree).
"""

from __future__ import annotations

import pytest

from synthetic_india.schemas.critic import CriticVerdict


def _verdict(
    *,
    persona_consistency: float = 8.0,
    sycophancy_score: float = 2.0,
    cultural_authenticity: float = 8.0,
    action_reasoning_alignment: float = 8.0,
    rule_flags: list[str] | None = None,
) -> CriticVerdict:
    return CriticVerdict(
        evaluation_id="e1",
        persona_id="p1",
        persona_consistency=persona_consistency,
        sycophancy_score=sycophancy_score,
        cultural_authenticity=cultural_authenticity,
        action_reasoning_alignment=action_reasoning_alignment,
        explanation="test",
        rule_flags=rule_flags or [],
    )


# ── compute_disagreement ─────────────────────────────────────


class TestComputeDisagreement:
    def test_identical_verdicts_zero_disagreement(self):
        from synthetic_india.agents.cross_model_critic import compute_disagreement

        a = _verdict()
        b = _verdict()
        result = compute_disagreement(a, b)
        assert result["max_abs_diff"] == 0.0
        assert result["verdicts_disagree"] is False

    def test_per_dim_diffs_are_absolute(self):
        from synthetic_india.agents.cross_model_critic import compute_disagreement

        a = _verdict(persona_consistency=8.0, cultural_authenticity=7.0)
        b = _verdict(persona_consistency=5.0, cultural_authenticity=9.0)
        result = compute_disagreement(a, b)
        assert result["per_dim"]["persona_consistency"] == 3.0
        assert result["per_dim"]["cultural_authenticity"] == 2.0
        assert result["max_abs_diff"] == 3.0

    def test_max_diff_picks_largest_dim(self):
        from synthetic_india.agents.cross_model_critic import compute_disagreement

        a = _verdict(sycophancy_score=1.0)
        b = _verdict(sycophancy_score=8.0)  # one model thinks it's sycophantic
        result = compute_disagreement(a, b)
        assert result["max_abs_diff"] == 7.0

    def test_verdicts_disagree_when_pass_vs_fail(self):
        from synthetic_india.agents.cross_model_critic import compute_disagreement

        # a passes (overall_quality >= 6), b fails
        a = _verdict(persona_consistency=9.0, cultural_authenticity=9.0)
        b = _verdict(persona_consistency=3.0, cultural_authenticity=3.0,
                     action_reasoning_alignment=3.0, sycophancy_score=8.0)
        assert a.passed is True
        assert b.passed is False
        result = compute_disagreement(a, b)
        assert result["verdicts_disagree"] is True


# ── cross_model_flags ────────────────────────────────────────


class TestCrossModelFlags:
    def test_aligned_verdicts_yield_no_flags(self):
        from synthetic_india.agents.cross_model_critic import cross_model_flags

        a = _verdict()
        b = _verdict(persona_consistency=7.5)  # tiny diff
        assert cross_model_flags(a, b) == []

    def test_large_dim_disagreement_flagged(self):
        from synthetic_india.agents.cross_model_critic import cross_model_flags

        a = _verdict(cultural_authenticity=9.0)
        b = _verdict(cultural_authenticity=4.0)  # 5-point gap
        flags = cross_model_flags(a, b, threshold=3.0)
        assert any("cross_model" in f.lower() and "disagree" in f.lower() for f in flags), flags
        # The flag should mention the offending dimension
        assert any("cultural_authenticity" in f for f in flags), flags

    def test_opposite_pass_fail_flagged_even_below_threshold(self):
        from synthetic_india.agents.cross_model_critic import cross_model_flags

        # Both verdicts within 3 points per-dim but accumulated to opposite passes
        a = _verdict(persona_consistency=8.0, cultural_authenticity=8.0,
                     action_reasoning_alignment=8.0, sycophancy_score=2.0)
        b = _verdict(persona_consistency=5.0, cultural_authenticity=5.0,
                     action_reasoning_alignment=5.0, sycophancy_score=5.0)
        # Per-dim diffs are exactly 3.0, but verdicts disagree on pass/fail
        assert a.passed is True
        assert b.passed is False
        flags = cross_model_flags(a, b, threshold=3.5)  # raise threshold so per-dim doesn't fire
        assert any("verdict" in f.lower() or "pass" in f.lower() for f in flags), flags

    def test_threshold_is_respected(self):
        from synthetic_india.agents.cross_model_critic import cross_model_flags

        a = _verdict(persona_consistency=8.0)
        b = _verdict(persona_consistency=6.0)  # 2-point gap
        # threshold 3.0 → no flag
        assert cross_model_flags(a, b, threshold=3.0) == []
        # threshold 1.0 → flag
        assert cross_model_flags(a, b, threshold=1.0) != []

    def test_flag_text_includes_diff_magnitude(self):
        from synthetic_india.agents.cross_model_critic import cross_model_flags

        a = _verdict(sycophancy_score=1.0)
        b = _verdict(sycophancy_score=9.0)
        flags = cross_model_flags(a, b)
        # Should embed the gap (8.0) so debugging output is informative
        joined = " ".join(flags)
        assert "8" in joined, f"expected diff magnitude in flag text: {flags}"


# ── Integration: rule_flags veto stays intact ───────────────


class TestRuleFlagsVeto:
    def test_disagreement_flags_force_passed_false(self):
        """Cross-model flags appended to rule_flags must veto passed."""
        a = _verdict(cultural_authenticity=9.0,
                     rule_flags=["cross_model_disagreement_cultural_authenticity_diff_5.0"])
        # Even though sub-scores would normally pass, rule_flags vetoes
        assert a.passed is False
