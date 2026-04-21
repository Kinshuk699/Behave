"""
Phase 4 — Persona contradictions: shadow archetype, value conflicts,
context modifiers.

Opus pressure-test issue addressed:
  #5 — personas read as flat / over-coherent. Real consumers hold
       competing values and behave differently under different contexts.

Three new optional fields on PersonaProfile:
  * shadow_archetype: Archetype | None
       Who this persona becomes when stressed, excited, or off-script.
  * value_conflicts: list[ValueConflict]
       Pairs of competing values with the contexts that activate each side.
  * context_modifiers: dict[str, BehaviorModifier]
       Named situations (e.g. 'end_of_month') that shift psychology dials.

All three are optional — existing persona JSONs continue to load.
The evaluator prompt block surfaces them when populated.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from synthetic_india.schemas.persona import Archetype, PersonaProfile


# ── Schema tests ─────────────────────────────────────────────


class TestSchemaShape:
    def test_value_conflict_requires_two_values_and_contexts(self):
        from synthetic_india.schemas.persona import ValueConflict

        vc = ValueConflict(
            value_a="thrift",
            value_b="status",
            context_a="grocery shopping with mother",
            context_b="dinner with college friends",
            dominant_side="situational",
        )
        assert vc.value_a == "thrift"
        assert vc.dominant_side == "situational"

    def test_value_conflict_dominant_side_validated(self):
        from synthetic_india.schemas.persona import ValueConflict

        with pytest.raises(ValidationError):
            ValueConflict(
                value_a="thrift",
                value_b="status",
                context_a="x",
                context_b="y",
                dominant_side="banana",  # not in {a, b, situational}
            )

    def test_behavior_modifier_clamps_deltas(self):
        from synthetic_india.schemas.persona import BehaviorModifier

        bm = BehaviorModifier(
            description="Salary just hit the account",
            dial_deltas={"impulse_tendency": 0.3, "price_sensitivity": -0.2},
        )
        assert bm.dial_deltas["impulse_tendency"] == 0.3

    def test_behavior_modifier_rejects_unknown_dial(self):
        from synthetic_india.schemas.persona import BehaviorModifier

        with pytest.raises(ValidationError):
            BehaviorModifier(
                description="x",
                dial_deltas={"made_up_dial": 0.1},
            )

    def test_behavior_modifier_rejects_out_of_range_delta(self):
        from synthetic_india.schemas.persona import BehaviorModifier

        with pytest.raises(ValidationError):
            BehaviorModifier(
                description="x",
                dial_deltas={"impulse_tendency": 2.0},  # outside [-1, 1]
            )

    def test_persona_profile_accepts_new_fields(self, sample_persona_kwargs):
        from synthetic_india.schemas.persona import (
            BehaviorModifier,
            ValueConflict,
        )

        persona = PersonaProfile(
            **sample_persona_kwargs,
            shadow_archetype=Archetype.IMPULSE_BUYER,
            value_conflicts=[
                ValueConflict(
                    value_a="family_security",
                    value_b="self_reward",
                    context_a="month-end groceries",
                    context_b="diwali shopping",
                    dominant_side="a",
                ),
            ],
            context_modifiers={
                "end_of_month": BehaviorModifier(
                    description="Bills cleared, salary not yet in",
                    dial_deltas={"price_sensitivity": 0.2, "impulse_tendency": -0.15},
                ),
            },
        )
        assert persona.shadow_archetype == Archetype.IMPULSE_BUYER.value
        assert persona.value_conflicts[0].value_a == "family_security"
        assert "end_of_month" in persona.context_modifiers

    def test_persona_profile_defaults_remain_backward_compatible(
        self, sample_persona_kwargs
    ):
        """Existing personas without the new fields still load."""
        persona = PersonaProfile(**sample_persona_kwargs)
        assert persona.shadow_archetype is None
        assert persona.value_conflicts == []
        assert persona.context_modifiers == {}


# ── Existing persona files still load ───────────────────────


class TestRealPersonaFilesLoad:
    def test_all_personas_in_data_dir_load_with_phase4_schema(self):
        from synthetic_india.engine.simulation import load_personas

        personas = load_personas()
        assert len(personas) > 0
        for p in personas:
            # Backward compat: all defaults are sensible
            assert p.shadow_archetype is None or p.shadow_archetype in [a.value for a in Archetype]
            assert isinstance(p.value_conflicts, list)
            assert isinstance(p.context_modifiers, dict)


# ── Prompt block surfaces new fields ────────────────────────


class TestPromptBlockRendering:
    def test_shadow_archetype_appears_in_prompt(self, sample_persona_kwargs):
        from synthetic_india.agents.persona_evaluator import _build_persona_block

        persona = PersonaProfile(
            **sample_persona_kwargs,
            shadow_archetype=Archetype.IMPULSE_BUYER,
        )
        block = _build_persona_block(persona)
        assert "shadow" in block.lower()
        assert "impulse_buyer" in block.lower() or "impulse buyer" in block.lower()

    def test_value_conflicts_appear_in_prompt(self, sample_persona_kwargs):
        from synthetic_india.agents.persona_evaluator import _build_persona_block
        from synthetic_india.schemas.persona import ValueConflict

        persona = PersonaProfile(
            **sample_persona_kwargs,
            value_conflicts=[
                ValueConflict(
                    value_a="thrift",
                    value_b="hospitality",
                    context_a="weekday dal-chawal",
                    context_b="guests visiting",
                    dominant_side="situational",
                ),
            ],
        )
        block = _build_persona_block(persona)
        assert "thrift" in block.lower()
        assert "hospitality" in block.lower()
        assert "guests visiting" in block.lower()

    def test_context_modifiers_appear_in_prompt(self, sample_persona_kwargs):
        from synthetic_india.agents.persona_evaluator import _build_persona_block
        from synthetic_india.schemas.persona import BehaviorModifier

        persona = PersonaProfile(
            **sample_persona_kwargs,
            context_modifiers={
                "after_a_long_day": BehaviorModifier(
                    description="Tired and craving comfort",
                    dial_deltas={"impulse_tendency": 0.25, "research_depth": -0.2},
                ),
            },
        )
        block = _build_persona_block(persona)
        assert "after_a_long_day" in block or "after a long day" in block.lower()
        assert "impulse_tendency" in block or "+0.25" in block or "0.25" in block

    def test_no_section_when_field_absent(self, sample_persona_kwargs):
        """No phantom 'Shadow Archetype' header when field is None."""
        from synthetic_india.agents.persona_evaluator import _build_persona_block

        persona = PersonaProfile(**sample_persona_kwargs)
        block = _build_persona_block(persona)
        assert "shadow" not in block.lower()
        assert "value conflicts" not in block.lower()
        assert "context modifiers" not in block.lower()


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def sample_persona_kwargs():
    """Minimal valid kwargs for a PersonaProfile, reused across tests."""
    from synthetic_india.schemas.persona import (
        Archetype,
        CityTier,
        Demographics,
        EmotionalProfile,
        Gender,
        IncomeSegment,
        MediaBehavior,
        PurchasePsychology,
    )

    return dict(
        persona_id="p_phase4",
        name="Test Persona",
        archetype=Archetype.PRAGMATIST,
        tagline="A test",
        demographics=Demographics(
            age=35,
            gender=Gender.FEMALE,
            city="Pune",
            city_tier=CityTier.TIER_1,
            state="Maharashtra",
            income_segment=IncomeSegment.MIDDLE,
        ),
        purchase_psychology=PurchasePsychology(
            price_sensitivity=0.5,
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
