"""
Phase 3 — Critic v2 deterministic rules + specificity check.

Opus pressure-test issues addressed:
  #4 — same-model bias / critic blind to bland correctness
  #9 — sycophancy escapes when LLM critic itself sycophants

Two new layers run BEFORE the LLM critic:
  Layer 1 — `run_pre_critic_checks()` returns rule violation flags
            (price-vs-income sanity, action-vs-score contradiction,
             score-inflation sycophancy).
  Layer 2 — `run_specificity_check()` returns flags when reasoning /
            verbatim lacks concrete signals (rupee, person, sensory,
            temporal) or contains forbidden consultant phrases.

Any non-empty flag list → CriticVerdict.passed forced to False.
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


# ── Builders ─────────────────────────────────────────────────


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
        emotional_profile=EmotionalProfile(
            aspiration_drivers=["comfort"],
            trust_signals=["reviews"],
            rejection_triggers=["fake claims"],
            emotional_hooks=["family"],
        ),
        media_behavior=MediaBehavior(
            platform_primary="Instagram",
            ad_tolerance=0.5,
            scroll_speed="moderate",
            video_preference=0.5,
            influencer_trust=0.4,
        ),
        backstory="A test persona for unit tests.",
        current_life_context="Testing.",
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


# ── Layer 1: deterministic rules ─────────────────────────────


class TestPreCriticRules:
    def test_price_income_sanity_flags_budget_buying_premium(self):
        """BUDGET income + premium category + PURCHASE_INTENT + high score with no objections → flag."""
        from synthetic_india.agents.critic_rules import run_pre_critic_checks

        persona = _persona(income=IncomeSegment.BUDGET, price_sens=0.9)
        ev = _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            sentiment=Sentiment.VERY_POSITIVE,
            overall_score=88.0,
            objections=[],
            category="luxury_skincare",
        )
        flags = run_pre_critic_checks(persona, ev)
        assert any("price" in f.lower() or "income" in f.lower() for f in flags), (
            f"expected price-income flag, got {flags}"
        )

    def test_price_income_sanity_silent_for_aligned_buyer(self):
        """PREMIUM income + premium category + purchase intent → no flag."""
        from synthetic_india.agents.critic_rules import run_pre_critic_checks

        persona = _persona(income=IncomeSegment.PREMIUM, price_sens=0.2)
        ev = _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            sentiment=Sentiment.VERY_POSITIVE,
            overall_score=85.0,
            category="luxury_skincare",
            reasoning="Good value at this price for me.",
        )
        flags = run_pre_critic_checks(persona, ev)
        assert not any("price" in f.lower() or "income" in f.lower() for f in flags), flags

    def test_action_score_contradiction_purchase_with_low_trust(self):
        """PURCHASE_INTENT with trust_score < 4 → contradiction flag."""
        from synthetic_india.agents.critic_rules import run_pre_critic_checks

        persona = _persona()
        ev = _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            trust=3.0,
            desire=8.0,
            overall_score=72.0,
        )
        flags = run_pre_critic_checks(persona, ev)
        assert any("contradict" in f.lower() or "alignment" in f.lower() for f in flags), flags

    def test_action_score_contradiction_scroll_past_with_high_score(self):
        """SCROLL_PAST/NEGATIVE_REACT but overall_score > 70 → contradiction flag."""
        from synthetic_india.agents.critic_rules import run_pre_critic_checks

        persona = _persona()
        ev = _eval(
            primary_action=ConsumerAction.SCROLL_PAST,
            sentiment=Sentiment.NEGATIVE,
            overall_score=82.0,
            attention=8.0,
            desire=8.0,
        )
        flags = run_pre_critic_checks(persona, ev)
        assert any("contradict" in f.lower() or "alignment" in f.lower() for f in flags), flags

    def test_score_inflation_flags_all_high_no_objections(self):
        """All 5 dim scores ≥ 8, overall ≥ 85, zero objections → inflation flag."""
        from synthetic_india.agents.critic_rules import run_pre_critic_checks

        persona = _persona()
        ev = _eval(
            primary_action=ConsumerAction.PURCHASE_INTENT,
            sentiment=Sentiment.VERY_POSITIVE,
            overall_score=92.0,
            attention=9.0,
            relevance=9.0,
            trust=8.5,
            desire=9.0,
            clarity=9.5,
            objections=[],
        )
        flags = run_pre_critic_checks(persona, ev)
        assert any("inflat" in f.lower() or "sycoph" in f.lower() for f in flags), flags

    def test_clean_evaluation_yields_no_rule_flags(self):
        """A normal, well-aligned evaluation should produce zero flags."""
        from synthetic_india.agents.critic_rules import run_pre_critic_checks

        persona = _persona()
        ev = _eval()  # default — moderate scores, has objections
        flags = run_pre_critic_checks(persona, ev)
        assert flags == [], flags


# ── Layer 2: specificity check ──────────────────────────────


class TestSpecificityCheck:
    def test_bland_consultant_speak_flagged(self):
        """Generic praise with forbidden phrases → flag."""
        from synthetic_india.agents.critic_rules import run_specificity_check

        ev = _eval(
            reasoning="The ad really resonates with me. It is well-crafted and speaks to me.",
            verbatim="This ad captures the essence of the brand beautifully.",
        )
        flags = run_specificity_check(ev)
        assert any("forbidden" in f.lower() or "consultant" in f.lower() for f in flags), flags

    def test_low_specificity_flagged(self):
        """No rupee, no person, no sensory, no temporal → specificity flag."""
        from synthetic_india.agents.critic_rules import run_specificity_check

        ev = _eval(
            reasoning="It seems okay. The product looks fine to me overall.",
            verbatim="Not bad, not great.",
            objections=[],
        )
        flags = run_specificity_check(ev)
        assert any("specific" in f.lower() or "vague" in f.lower() for f in flags), flags

    def test_specific_evaluation_passes(self):
        """Reasoning with rupee + family + temporal anchor → no flag."""
        from synthetic_india.agents.critic_rules import run_specificity_check

        ev = _eval(
            reasoning=(
                "₹450 is a lot for a face wash. My husband already complained "
                "last month when I bought the Lakme one for ₹320."
            ),
            verbatim="Arre, itna mehenga? Diwali ke baad sochungi maybe.",
        )
        flags = run_specificity_check(ev)
        assert flags == [], flags

    def test_rupee_alone_insufficient_without_other_signals(self):
        """A single signal isn't enough — need ≥ 2 specificity markers."""
        from synthetic_india.agents.critic_rules import run_specificity_check

        ev = _eval(
            reasoning="It costs ₹500 which feels reasonable.",
            verbatim="Okay product.",
            objections=[],
        )
        flags = run_specificity_check(ev)
        assert any("specific" in f.lower() or "vague" in f.lower() for f in flags), flags


# ── Integration: CriticVerdict.passed honours rule_flags ────


class TestVerdictHonoursFlags:
    def test_verdict_with_rule_flags_fails_even_with_high_quality(self):
        """If rule_flags is non-empty, passed must be False regardless of sub-scores."""
        from synthetic_india.schemas.critic import CriticVerdict

        v = CriticVerdict(
            evaluation_id="e1",
            persona_id="p1",
            persona_consistency=10.0,
            sycophancy_score=0.0,
            cultural_authenticity=10.0,
            action_reasoning_alignment=10.0,
            explanation="LLM thought it was perfect",
            rule_flags=["price_income_mismatch"],
        )
        assert v.passed is False, "rule_flags must veto passed"

    def test_verdict_without_rule_flags_uses_quality_threshold(self):
        """Empty rule_flags → existing quality-threshold behaviour preserved."""
        from synthetic_india.schemas.critic import CriticVerdict

        v = CriticVerdict(
            evaluation_id="e1",
            persona_id="p1",
            persona_consistency=8.0,
            sycophancy_score=2.0,
            cultural_authenticity=8.0,
            action_reasoning_alignment=8.0,
            explanation="ok",
        )
        assert v.passed is True
