"""
Phase 6 — Critic evaluation harness.

Wraps the deterministic critic layers (`critic_rules`) in a golden-set
benchmark so threshold/regex changes get measured against precision,
recall, and false-positive rate.

No LLM calls. Fast, deterministic, free to run in CI.

Public API:
  run_critic_benchmark(bad_cases, good_cases) -> BenchmarkResult

  bad_cases  : list[(label, persona, evaluation)] — MUST be flagged
  good_cases : list[(label, persona, evaluation)] — must NOT be flagged
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from synthetic_india.agents.critic_rules import (
    run_pre_critic_checks,
    run_specificity_check,
)
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.persona import PersonaProfile


@dataclass
class BenchmarkResult:
    """Aggregated metrics from a benchmark run."""

    total_bad: int
    total_good: int
    true_positives: int
    false_negatives: int
    false_positives: int
    true_negatives: int
    precision: float
    recall: float
    false_positive_rate: float
    per_case: list[dict[str, Any]] = field(default_factory=list)


def _all_flags(persona: PersonaProfile, evaluation: PersonaEvaluation) -> list[str]:
    """Run both deterministic layers and return the merged flag list."""
    return run_pre_critic_checks(persona, evaluation) + run_specificity_check(
        evaluation
    )


def run_critic_benchmark(
    bad_cases: list[tuple[str, PersonaProfile, PersonaEvaluation]],
    good_cases: list[tuple[str, PersonaProfile, PersonaEvaluation]],
) -> BenchmarkResult:
    per_case: list[dict[str, Any]] = []
    tp = fn = fp = tn = 0

    for label, persona, evaluation in bad_cases:
        flags = _all_flags(persona, evaluation)
        flagged = bool(flags)
        per_case.append(
            {
                "label": label,
                "expected_flag": True,
                "actual_flag": flagged,
                "flags": flags,
            }
        )
        if flagged:
            tp += 1
        else:
            fn += 1

    for label, persona, evaluation in good_cases:
        flags = _all_flags(persona, evaluation)
        flagged = bool(flags)
        per_case.append(
            {
                "label": label,
                "expected_flag": False,
                "actual_flag": flagged,
                "flags": flags,
            }
        )
        if flagged:
            fp += 1
        else:
            tn += 1

    total_flagged = tp + fp
    total_bad = tp + fn
    total_good = fp + tn

    precision = tp / total_flagged if total_flagged else 0.0
    recall = tp / total_bad if total_bad else 0.0
    fpr = fp / total_good if total_good else 0.0

    return BenchmarkResult(
        total_bad=total_bad,
        total_good=total_good,
        true_positives=tp,
        false_negatives=fn,
        false_positives=fp,
        true_negatives=tn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        false_positive_rate=round(fpr, 4),
        per_case=per_case,
    )
