"""
Phase 6 — Critic evaluation harness.

Phases 3 and 3.5 added new failure-detection layers but we never measured
their actual catch rate. This harness wraps the deterministic rule layers
(critic_rules.run_pre_critic_checks + run_specificity_check) in a
golden-set benchmark so any future threshold change gets measured.

No LLM calls here — fast, deterministic, free to run in CI.

Public API:
  run_critic_benchmark(bad_cases, good_cases) -> BenchmarkResult
      Returns precision, recall, FPR, per-case verdicts.

Targets enforced by tests:
  recall on bad cases    ≥ 0.80   (catch most bad)
  FPR on good cases      ≤ 0.20   (don't flag too many good)
  precision overall      ≥ 0.80
"""

from __future__ import annotations

import pytest

from synthetic_india.schemas.evaluation import (
    ConsumerAction,
    PersonaEvaluation,
    Sentiment,
)
from synthetic_india.schemas.persona import (
    CityTier,
    Demographics,
    EmotionalProfile,
    Gender,
    IncomeSegment,
    MediaBehavior,
    PersonaProfile,
    PurchasePsychology,
)


# ── Builders (inlined; tests/ is not a package) ─────────────


def _persona(
    persona_id: str = "p_test",
    income: IncomeSegment = IncomeSegment.MIDDLE,
    price_sens: float = 0.5,
) -> PersonaProfile:
    return PersonaProfile(
        persona_id=persona_id,
        archetype="pragmatist",
        name="Test Persona",
        tagline="A test",
        demographics=Demographics(
            age=35,
            gender=Gender.FEMALE,
            city="Pune",
            city_tier=CityTier.TIER_1,
            state="Maharashtra",
            income_segment=income,
        ),
        purchase_psychology=PurchasePsychology(
            price_sensitivity=price_sens,
            brand_loyalty=0.5,
            impulse_tendency=0.3,
            social_proof_need=0.4,
            research_depth=0.6,
            risk_tolerance=0.4,
            decision_speed="moderate",
            deal_sensitivity=0.5,
        ),
        media_behavior=MediaBehavior(
            platform_primary="Instagram",
            ad_tolerance=0.5,
            scroll_speed="moderate",
            video_preference=0.5,
            influencer_trust=0.4,
        ),
        emotional_profile=EmotionalProfile(
            aspiration_drivers=["comfort"],
            trust_signals=["reviews"],
            rejection_triggers=["fake claims"],
            emotional_hooks=["family"],
        ),
        backstory="A pragmatic shopper from Pune.",
        current_life_context="Mid-month, normal routine.",
        inner_monologue_style="practical",
    )


def _eval(
    *,
    primary_action: ConsumerAction = ConsumerAction.READ,
    sentiment: Sentiment = Sentiment.POSITIVE,
    overall_score: float = 70.0,
    attention: float = 7.0,
    relevance: float = 7.0,
    trust: float = 7.0,
    desire: float = 7.0,
    clarity: float = 7.0,
    objections: list[str] | None = None,
    reasoning: str = "Reasonable price for the quality offered.",
    verbatim: str = "Looks decent, will think about it.",
    category: str = "skincare",
) -> PersonaEvaluation:
    return PersonaEvaluation(
        evaluation_id="e1",
        run_id="r1",
        creative_id="c1",
        persona_id="p_test",
        primary_action=primary_action,
        sentiment=sentiment,
        overall_score=overall_score,
        attention_score=attention,
        relevance_score=relevance,
        trust_score=trust,
        desire_score=desire,
        clarity_score=clarity,
        first_impression="ok",
        reasoning=reasoning,
        objections=objections if objections is not None else ["a bit pricey"],
        verbatim_reaction=verbatim,
        importance_score=5.0,
        category=category,
        brand="TestBrand",
        key_themes=["price"],
    )


# ── Golden set: known-bad evaluations ───────────────────────


def _bad_cases() -> list[tuple[str, object, object]]:
    """Return list of (label, persona, evaluation) the harness MUST flag.

    Each case targets a specific failure mode the rule layers should catch.
    """
    cases: list[tuple[str, object, object]] = []

    # Bad #1 — score inflation sycophancy
    cases.append((
        "score_inflation_all_high",
        _persona(),
        _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            sentiment=Sentiment.VERY_POSITIVE,
            overall_score=92.0,
            attention=9.0, relevance=9.0, trust=8.5, desire=9.0, clarity=9.5,
            objections=[],
            reasoning="Great product. Very strong messaging. Will buy.",
            verbatim="Loved everything about this!",
        ),
    ))

    # Bad #2 — purchase intent with low trust (action/score contradiction)
    cases.append((
        "purchase_with_low_trust",
        _persona(),
        _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            trust=2.0, desire=8.0,
            overall_score=72.0,
            reasoning="₹500 mein paaye to maza aa jaye, even though I don't trust the brand.",
            verbatim="Yaar le leta hoon test karne ke liye.",
        ),
    ))

    # Bad #3 — scroll past with high overall score
    cases.append((
        "scroll_past_with_high_score",
        _persona(),
        _eval(
            primary_action=ConsumerAction.SCROLL_PAST,
            sentiment=Sentiment.NEGATIVE,
            overall_score=85.0,
            attention=8.0, desire=8.0,
            reasoning="₹400 ki face wash. My husband would notice last month I bought one for ₹250.",
            verbatim="Skip kar deti hoon.",
        ),
    ))

    # Bad #4 — budget buyer enthusiastically buying premium category
    cases.append((
        "budget_buyer_premium",
        _persona(income=IncomeSegment.BUDGET, price_sens=0.9),
        _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            sentiment=Sentiment.VERY_POSITIVE,
            overall_score=88.0,
            attention=8.0, relevance=8.5, trust=8.0, desire=9.0, clarity=8.5,
            objections=[],
            category="luxury_skincare",
            reasoning="The product looks lovely and I want to try it.",
            verbatim="Le hi leti hoon.",
        ),
    ))

    # Bad #5 — pure consultant-speak
    cases.append((
        "consultant_speak",
        _persona(),
        _eval(
            reasoning="The ad really resonates with me. It is well-crafted and speaks to me on every level.",
            verbatim="This captures the essence of the brand beautifully.",
        ),
    ))

    # Bad #6 — vague, no anchors
    cases.append((
        "vague_no_anchors",
        _persona(),
        _eval(
            reasoning="It seems okay. The product looks fine to me overall.",
            verbatim="Not bad, not great.",
            objections=[],
        ),
    ))

    # Bad #7 — single rupee mention, otherwise vague
    cases.append((
        "single_signal_only",
        _persona(),
        _eval(
            reasoning="It costs ₹500 which feels reasonable.",
            verbatim="Okay product.",
            objections=[],
        ),
    ))

    # Bad #8 — purchase with low desire
    cases.append((
        "purchase_with_low_desire",
        _persona(),
        _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            trust=8.0, desire=3.0,
            overall_score=65.0,
            reasoning="Trust the brand but ₹600 seems a lot. My sister bought last week.",
            verbatim="Soch ke leti hoon.",
        ),
    ))

    # Bad #9 — negative reaction with positive sentiment + high score
    cases.append((
        "negative_action_high_score",
        _persona(),
        _eval(
            primary_action=ConsumerAction.NEGATIVE_REACT,
            sentiment=Sentiment.POSITIVE,
            overall_score=78.0,
            reasoning="₹300 dishwash for kids? My mother would slap me. We always used Vim.",
            verbatim="Reject.",
        ),
    ))

    # Bad #10 — generic praise with forbidden phrase
    cases.append((
        "forbidden_phrase_buried",
        _persona(),
        _eval(
            reasoning=(
                "This ad strikes a chord and tugs at the heartstrings of "
                "every Indian. Powerful messaging."
            ),
            verbatim="Beautiful work by the brand.",
        ),
    ))

    return cases


# ── Golden set: known-good evaluations ──────────────────────


def _good_cases() -> list[tuple[str, object, object]]:
    """Return list of (label, persona, evaluation) the harness must NOT flag."""
    cases: list[tuple[str, object, object]] = []

    # Good #1 — moderate scores with real objection, specific reasoning
    cases.append((
        "moderate_specific",
        _persona(),
        _eval(
            primary_action=ConsumerAction.READ,
            sentiment=Sentiment.NEUTRAL,
            overall_score=65.0,
            attention=7.0, relevance=6.0, trust=6.5, desire=5.5, clarity=7.0,
            objections=["price seems high for the size"],
            reasoning=(
                "₹450 for 200ml is steep. My mother always bought the "
                "Patanjali version for ₹180 last Diwali."
            ),
            verbatim="Soch ke leti hoon, abhi nahi.",
        ),
    ))

    # Good #2 — premium buyer purchasing premium (income-aligned)
    cases.append((
        "premium_aligned",
        _persona(income=IncomeSegment.PREMIUM, price_sens=0.2),
        _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            sentiment=Sentiment.VERY_POSITIVE,
            overall_score=82.0,
            attention=8.0, relevance=7.5, trust=8.0, desire=8.5, clarity=7.0,
            objections=["wish there was a smaller trial size"],
            category="luxury_skincare",
            reasoning=(
                "₹2400 is reasonable for the brand. My husband uses the "
                "men's range, I trust the lab certifications."
            ),
            verbatim="Order kar deti hoon, weekend tak aa jayega.",
        ),
    ))

    # Good #3 — scroll past, low scores, consistent
    cases.append((
        "scroll_past_consistent",
        _persona(),
        _eval(
            primary_action=ConsumerAction.SCROLL_PAST,
            sentiment=Sentiment.NEGATIVE,
            overall_score=35.0,
            attention=3.0, relevance=3.5, trust=4.0, desire=2.5, clarity=5.0,
            objections=["language too English", "no price shown"],
            reasoning=(
                "₹0 information given. My friend Priya wasted money on "
                "such ads last summer. Skip."
            ),
            verbatim="Scroll, scroll.",
        ),
    ))

    # Good #4 — engaged but skeptical, mentions husband + rupee + temporal
    cases.append((
        "engaged_skeptical",
        _persona(),
        _eval(
            primary_action=ConsumerAction.SAVE,
            sentiment=Sentiment.POSITIVE,
            overall_score=68.0,
            attention=7.5, relevance=7.0, trust=6.0, desire=7.0, clarity=7.5,
            objections=["want to compare with the other brand", "delivery time unclear"],
            reasoning=(
                "₹650 for the combo is fair. My husband mentioned this "
                "brand last week after his colleague recommended."
            ),
            verbatim="Save kar deti hoon, weekend mein review padhungi.",
        ),
    ))

    # Good #5 — purchase intent with strong trust + desire alignment
    cases.append((
        "purchase_well_aligned",
        _persona(),
        _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            sentiment=Sentiment.POSITIVE,
            overall_score=75.0,
            attention=7.0, relevance=8.0, trust=8.0, desire=8.0, clarity=7.5,
            objections=["delivery in 5 days is slow"],
            reasoning=(
                "₹350 for 500g is exactly what we need. My daughter "
                "loves this taste, we used Maggi for years."
            ),
            verbatim="Le leti hoon, monthly grocery mein add.",
        ),
    ))

    # Good #6 — negative reaction with consistent low scores
    cases.append((
        "negative_consistent",
        _persona(),
        _eval(
            primary_action=ConsumerAction.NEGATIVE_REACT,
            sentiment=Sentiment.VERY_NEGATIVE,
            overall_score=20.0,
            attention=4.0, relevance=2.0, trust=2.0, desire=1.5, clarity=5.0,
            objections=["sounds fake", "celebrity overuse"],
            reasoning=(
                "₹2000 cream from a 22-year-old? My mother taught me to "
                "spot these scams. Reminds me of fairness creams in 2015."
            ),
            verbatim="Bakwaas. Block kar diya.",
        ),
    ))

    # Good #7 — pause, neutral, real-feeling
    cases.append((
        "pause_neutral",
        _persona(),
        _eval(
            primary_action=ConsumerAction.PAUSE,
            sentiment=Sentiment.NEUTRAL,
            overall_score=55.0,
            attention=6.0, relevance=5.5, trust=5.5, desire=5.0, clarity=6.5,
            objections=["not sure if it works for my skin type"],
            reasoning=(
                "₹220 is okay but my sister-in-law tried last Holi and "
                "broke out. I'll wait."
            ),
            verbatim="Hmm. Dekhte hain.",
        ),
    ))

    # Good #8 — share, with social context
    cases.append((
        "share_social",
        _persona(),
        _eval(
            primary_action=ConsumerAction.SHARE,
            sentiment=Sentiment.POSITIVE,
            overall_score=72.0,
            attention=7.0, relevance=7.5, trust=7.0, desire=6.5, clarity=8.0,
            objections=["a bit too cheerful for the topic"],
            reasoning=(
                "₹0 cost to me but my college friends WhatsApp group "
                "would love this — Diwali memes are starting."
            ),
            verbatim="Forward kar deti hoon group mein.",
        ),
    ))

    return cases


# ── Tests on the harness itself ─────────────────────────────


class TestBenchmark:
    def test_benchmark_function_exists(self):
        from synthetic_india.agents.critic_benchmark import run_critic_benchmark

        result = run_critic_benchmark([], [])
        assert hasattr(result, "precision")
        assert hasattr(result, "recall")
        assert hasattr(result, "false_positive_rate")
        assert hasattr(result, "per_case")

    def test_recall_on_bad_cases_meets_threshold(self):
        """The deterministic critic must catch ≥ 80% of known-bad cases."""
        from synthetic_india.agents.critic_benchmark import run_critic_benchmark

        result = run_critic_benchmark(_bad_cases(), _good_cases())
        assert result.recall >= 0.80, (
            f"recall {result.recall:.2f} below 0.80; "
            f"missed: {[c['label'] for c in result.per_case if c['expected_flag'] and not c['actual_flag']]}"
        )

    def test_false_positive_rate_on_good_cases_within_threshold(self):
        """≤ 20% of known-good cases may be (incorrectly) flagged."""
        from synthetic_india.agents.critic_benchmark import run_critic_benchmark

        result = run_critic_benchmark(_bad_cases(), _good_cases())
        assert result.false_positive_rate <= 0.20, (
            f"FPR {result.false_positive_rate:.2f} above 0.20; "
            f"false positives: {[c['label'] for c in result.per_case if not c['expected_flag'] and c['actual_flag']]}"
        )

    def test_precision_overall_meets_threshold(self):
        from synthetic_india.agents.critic_benchmark import run_critic_benchmark

        result = run_critic_benchmark(_bad_cases(), _good_cases())
        assert result.precision >= 0.80, (
            f"precision {result.precision:.2f} below 0.80"
        )

    def test_per_case_includes_flag_details(self):
        from synthetic_india.agents.critic_benchmark import run_critic_benchmark

        result = run_critic_benchmark(_bad_cases()[:1], _good_cases()[:1])
        assert len(result.per_case) == 2
        for entry in result.per_case:
            assert "label" in entry
            assert "expected_flag" in entry
            assert "actual_flag" in entry
            assert "flags" in entry  # the actual flag list

    def test_empty_input_returns_zero_metrics(self):
        from synthetic_india.agents.critic_benchmark import run_critic_benchmark

        result = run_critic_benchmark([], [])
        assert result.recall == 0.0
        assert result.precision == 0.0
        assert result.false_positive_rate == 0.0
        assert result.per_case == []
