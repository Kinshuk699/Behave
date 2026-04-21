"""
Phase 3 — Critic v2 deterministic pre-checks.

Two pure-Python layers that run BEFORE the LLM critic. They catch failure
modes the LLM itself is bad at noticing — bland-but-correct outputs,
score inflation, and action/score contradictions. Any flag returned here
becomes a `CriticVerdict.rule_flags` entry and forces `passed = False`.

Public API:
  run_pre_critic_checks(persona, evaluation) -> list[str]
  run_specificity_check(evaluation) -> list[str]
"""

from __future__ import annotations

import re

from synthetic_india.schemas.evaluation import (
    ConsumerAction,
    PersonaEvaluation,
    Sentiment,
)
from synthetic_india.schemas.persona import IncomeSegment, PersonaProfile


# ── Layer 1: deterministic rules ─────────────────────────────

_LOW_INCOME = {IncomeSegment.BUDGET.value, IncomeSegment.LOWER_MIDDLE.value}
_PREMIUM_CATEGORY_MARKERS = (
    "luxury",
    "premium",
    "designer",
    "imported",
    "high_end",
    "high-end",
)

_PURCHASE_ACTIONS = {
    ConsumerAction.PURCHASE_INTENT.value,
    ConsumerAction.CLICK.value,
}
_NEGATIVE_ACTIONS = {
    ConsumerAction.SCROLL_PAST.value,
    ConsumerAction.NEGATIVE_REACT.value,
}


def _enum_value(field) -> str:
    """Persona/eval models use `use_enum_values=True`, but be defensive."""
    return field.value if hasattr(field, "value") else str(field)


def _is_premium_category(category: str) -> bool:
    cat = category.lower()
    return any(marker in cat for marker in _PREMIUM_CATEGORY_MARKERS)


def _check_price_income_sanity(
    persona: PersonaProfile, ev: PersonaEvaluation
) -> str | None:
    """Budget buyer enthusiastically committing to premium category with no objections."""
    income = _enum_value(persona.demographics.income_segment)
    if income not in _LOW_INCOME:
        return None
    if not _is_premium_category(ev.category):
        return None
    if _enum_value(ev.primary_action) not in _PURCHASE_ACTIONS:
        return None
    if ev.overall_score < 80:
        return None
    if ev.objections:  # any acknowledged tension is enough
        return None
    return (
        f"price_income_mismatch: {income} buyer with no objections "
        f"committing to {ev.category} at score {ev.overall_score}"
    )


def _check_action_score_contradiction(ev: PersonaEvaluation) -> str | None:
    """Action vs sub-scores must be coherent."""
    action = _enum_value(ev.primary_action)
    if action in _PURCHASE_ACTIONS:
        if ev.trust_score < 4.0:
            return (
                f"action_alignment_contradict: {action} with trust_score "
                f"{ev.trust_score} (< 4)"
            )
        if ev.desire_score < 4.0:
            return (
                f"action_alignment_contradict: {action} with desire_score "
                f"{ev.desire_score} (< 4)"
            )
    if action in _NEGATIVE_ACTIONS and ev.overall_score > 70:
        return (
            f"action_alignment_contradict: {action} with overall_score "
            f"{ev.overall_score} (> 70)"
        )
    return None


def _check_score_inflation(ev: PersonaEvaluation) -> str | None:
    """All five sub-scores high, overall high, zero objections → sycophancy."""
    high = (
        ev.attention_score >= 8.0
        and ev.relevance_score >= 8.0
        and ev.trust_score >= 8.0
        and ev.desire_score >= 8.0
        and ev.clarity_score >= 8.0
    )
    if high and ev.overall_score >= 85 and not ev.objections:
        return (
            "score_inflation_sycophancy: all dim scores >= 8, overall "
            f"{ev.overall_score}, zero objections"
        )
    return None


def run_pre_critic_checks(
    persona: PersonaProfile, evaluation: PersonaEvaluation
) -> list[str]:
    """Return a list of deterministic rule violations. Empty list = pass."""
    flags: list[str] = []
    for check in (
        _check_price_income_sanity(persona, evaluation),
        _check_action_score_contradiction(evaluation),
        _check_score_inflation(evaluation),
    ):
        if check:
            flags.append(check)
    return flags


# ── Layer 2: specificity check ───────────────────────────────

# Forbidden consultant / focus-group phrases.
_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "resonates with",
    "well-crafted",
    "well crafted",
    "speaks to me",
    "captures the essence",
    "compelling narrative",
    "powerful messaging",
    "strikes a chord",
    "tugs at the heartstrings",
    "leaves a lasting impression",
)

# Patterns that prove the persona thought concretely.
_RUPEE_RE = re.compile(r"(₹|rs\.?\s*\d|rupee|inr\s*\d)", re.IGNORECASE)
_PERSON_RE = re.compile(
    r"\b(my\s+(wife|husband|mother|father|mom|dad|son|daughter|sister|"
    r"brother|kids?|child|children|nani|dadi|nana|dada|bhai|behen|"
    r"colleague|boss|friend|neighbour|neighbor|landlord|maid|driver))\b",
    re.IGNORECASE,
)
_SENSORY_RE = re.compile(
    r"\b(taste[sd]?|smell[sd]?|smelt|smelled|sound[sd]?|colou?r[sd]?|"
    r"texture|touch[ed]?|saw|loud|bright|sweet|salty|spicy|fragrant|"
    r"crunch[yi]?|soft|rough|sticky|oily|greasy|silky|smooth)\b",
    re.IGNORECASE,
)
_TEMPORAL_RE = re.compile(
    r"\b(yesterday|today|tomorrow|last\s+(week|month|year|diwali|holi|"
    r"eid|christmas)|next\s+(week|month|festival)|this\s+(morning|"
    r"evening|weekend)|diwali|holi|eid|onam|pongal|navratri|raksha\s+"
    r"bandhan|monsoon|summer|winter|festival|childhood|school\s+days?|"
    r"college\s+days?|when\s+i\s+was)\b",
    re.IGNORECASE,
)

_SPECIFICITY_THRESHOLD = 2  # need at least N distinct signal types


def run_specificity_check(evaluation: PersonaEvaluation) -> list[str]:
    """Return flags when reasoning/verbatim is bland or consultant-speak."""
    flags: list[str] = []
    text = f"{evaluation.reasoning}\n{evaluation.verbatim_reaction}"
    lower = text.lower()

    forbidden_hits = [p for p in _FORBIDDEN_PHRASES if p in lower]
    if forbidden_hits:
        flags.append(
            f"forbidden_consultant_phrase: {', '.join(sorted(set(forbidden_hits)))}"
        )

    signals = {
        "rupee": bool(_RUPEE_RE.search(text)),
        "person": bool(_PERSON_RE.search(text)),
        "sensory": bool(_SENSORY_RE.search(text)),
        "temporal": bool(_TEMPORAL_RE.search(text)),
    }
    hit_count = sum(signals.values())
    if hit_count < _SPECIFICITY_THRESHOLD:
        present = [k for k, v in signals.items() if v] or ["none"]
        flags.append(
            f"vague_low_specificity: only {hit_count} signal(s) "
            f"({', '.join(present)}); need >= {_SPECIFICITY_THRESHOLD}"
        )

    return flags
