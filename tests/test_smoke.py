"""Smoke tests — all local, zero API calls."""

from io import StringIO

from rich.console import Console

from synthetic_india.schemas.persona import PersonaProfile
from synthetic_india.schemas.creative import CreativeCard
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.memory import MemoryNode, MemoryStreamState
from synthetic_india.schemas.recommendation import AgentRecommendation
from synthetic_india.memory.stream import MemoryStream
from synthetic_india.memory.retrieval import MemoryRetriever, ReflectionEngine
from synthetic_india.engine.cohort import select_cohort
from synthetic_india.engine.simulation import load_personas
from synthetic_india.cli import build_demo_creatives, print_run_header, print_run_summary
from synthetic_india.pipeline.silver import validate_persona, validate_creative_card
from synthetic_india.schemas.recommendation import RunMetadata


# ── Critic schema tests ──────────────────────────────────────


def test_critic_verdict_construction():
    """CriticVerdict should accept 4 sub-scores and compute overall_quality + passed."""
    from synthetic_india.schemas.critic import CriticVerdict

    verdict = CriticVerdict(
        evaluation_id="eval_001",
        persona_id="researcher_delhi_01",
        persona_consistency=8.0,
        sycophancy_score=2.0,  # low = good (genuine)
        cultural_authenticity=7.5,
        action_reasoning_alignment=9.0,
        explanation="Evaluation is consistent with researcher persona profile.",
        flags=[],
        model_used="claude-sonnet-4-20250514",
        cost_usd=0.003,
    )

    assert verdict.passed is True  # high quality → should pass
    assert 0 <= verdict.overall_quality <= 10
    assert verdict.evaluation_id == "eval_001"


def test_critic_verdict_fails_sycophantic():
    """A highly sycophantic eval should fail the critic."""
    from synthetic_india.schemas.critic import CriticVerdict

    verdict = CriticVerdict(
        evaluation_id="eval_002",
        persona_id="skeptic_mumbai_01",
        persona_consistency=3.0,
        sycophancy_score=9.0,  # high = bad (sycophantic)
        cultural_authenticity=4.0,
        action_reasoning_alignment=3.0,
        explanation="Skeptic persona gave unrealistically glowing review.",
        flags=["sycophancy_detected", "persona_inconsistency"],
        model_used="claude-sonnet-4-20250514",
        cost_usd=0.003,
    )

    assert verdict.passed is False  # low quality → should fail
    assert verdict.overall_quality < 6.0


def test_critic_run_summary_rollup():
    """CriticRunSummary should aggregate verdicts and compute contribution breakdown."""
    from synthetic_india.schemas.critic import CriticVerdict, CriticRunSummary

    v1 = CriticVerdict(
        evaluation_id="eval_001",
        persona_id="researcher_delhi_01",
        persona_consistency=8.0,
        sycophancy_score=2.0,
        cultural_authenticity=7.0,
        action_reasoning_alignment=9.0,
        explanation="Good.",
        flags=[],
        model_used="claude-sonnet-4-20250514",
        cost_usd=0.003,
    )
    v2 = CriticVerdict(
        evaluation_id="eval_002",
        persona_id="skeptic_mumbai_01",
        persona_consistency=3.0,
        sycophancy_score=9.0,
        cultural_authenticity=4.0,
        action_reasoning_alignment=3.0,
        explanation="Bad.",
        flags=["sycophancy_detected"],
        model_used="claude-sonnet-4-20250514",
        cost_usd=0.003,
    )

    summary = CriticRunSummary.from_verdicts(run_id="run_001", verdicts=[v1, v2])

    assert summary.total_evaluated == 2
    assert summary.total_passed == 1
    assert summary.total_failed == 1
    assert 0 < summary.pass_rate < 1.0
    assert len(summary.quality_contributions) == 2
    # Each contribution has persona_id and contribution value
    persona_ids = [c["persona_id"] for c in summary.quality_contributions]
    assert "researcher_delhi_01" in persona_ids
    assert "skeptic_mumbai_01" in persona_ids


def test_critic_model_in_config():
    """LLMConfig should have a critic_model field defaulting to Sonnet."""
    from synthetic_india.config import LLMConfig

    config = LLMConfig()
    assert hasattr(config, "critic_model")
    assert "sonnet" in config.critic_model.lower() or "claude" in config.critic_model.lower()


def test_build_critic_prompt_contains_key_context():
    """build_critic_prompt should include persona profile, evaluation data, and scoring instructions."""
    from synthetic_india.agents.critic_agent import build_critic_prompt
    from synthetic_india.schemas.evaluation import PersonaEvaluation

    personas = load_personas()
    persona = personas[0]  # researcher

    evaluation = PersonaEvaluation(
        evaluation_id="eval_test_001",
        run_id="run_test",
        creative_id="creative_test",
        persona_id=persona.persona_id,
        primary_action="read",
        sentiment="positive",
        overall_score=72.0,
        attention_score=7.0,
        relevance_score=8.0,
        trust_score=6.5,
        desire_score=5.0,
        clarity_score=8.0,
        first_impression="Looks like a clean product page",
        reasoning="I'd read more because the ingredients list is transparent.",
        objections=["Price seems high for 10ml"],
        what_would_change_mind="Clinical trial data",
        verbatim_reaction="Ingredients are good but I need to check reviews first.",
        importance_score=6.0,
        category="skincare",
        brand="Minimalist",
        key_themes=["transparency", "ingredients"],
    )

    system, prompt = build_critic_prompt(persona=persona, evaluation=evaluation)

    # System prompt should mention critic role
    assert "critic" in system.lower() or "quality" in system.lower()
    # Prompt should contain persona identity
    assert persona.persona_id in prompt
    assert persona.archetype in prompt
    # Prompt should contain evaluation data
    assert "read" in prompt  # primary_action
    assert "72" in prompt  # overall_score
    assert "transparent" in prompt or "ingredients" in prompt  # reasoning content
    # Prompt should ask for the 4 quality dimensions
    assert "persona_consistency" in prompt or "persona consistency" in prompt.lower()
    assert "sycophancy" in prompt.lower()
    assert "cultural" in prompt.lower()
    assert "action" in prompt.lower() and "reasoning" in prompt.lower()


def test_summarize_run_via_agent():
    """summarize_run() in critic_agent should produce correct CriticRunSummary."""
    from synthetic_india.agents.critic_agent import summarize_run
    from synthetic_india.schemas.critic import CriticVerdict, CriticRunSummary

    verdicts = [
        CriticVerdict(
            evaluation_id="e1", persona_id="researcher_delhi_01",
            persona_consistency=8.0, sycophancy_score=2.0,
            cultural_authenticity=7.0, action_reasoning_alignment=9.0,
            explanation="Good.", flags=[], model_used="test", cost_usd=0.001,
        ),
        CriticVerdict(
            evaluation_id="e2", persona_id="skeptic_mumbai_01",
            persona_consistency=3.0, sycophancy_score=9.0,
            cultural_authenticity=4.0, action_reasoning_alignment=3.0,
            explanation="Bad.", flags=["sycophancy_detected"], model_used="test", cost_usd=0.001,
        ),
        CriticVerdict(
            evaluation_id="e3", persona_id="brand_loyalist_pune_01",
            persona_consistency=7.0, sycophancy_score=3.0,
            cultural_authenticity=8.0, action_reasoning_alignment=7.5,
            explanation="Solid.", flags=[], model_used="test", cost_usd=0.001,
        ),
    ]

    summary = summarize_run(run_id="run_test", verdicts=verdicts)

    assert isinstance(summary, CriticRunSummary)
    assert summary.total_evaluated == 3
    assert summary.total_passed == 2  # researcher + loyalist pass, skeptic fails
    assert summary.total_failed == 1
    assert abs(summary.pass_rate - 2 / 3) < 0.01
    # Averages should be computed correctly
    assert summary.avg_persona_consistency == round((8.0 + 3.0 + 7.0) / 3, 2)
    assert summary.avg_sycophancy_score == round((2.0 + 9.0 + 3.0) / 3, 2)
    # Contributions should sum conceptually
    assert len(summary.quality_contributions) == 3
    total_contrib = sum(c["contribution"] for c in summary.quality_contributions)
    assert total_contrib > 0


def test_simulation_imports_critic():
    """simulation module should import and expose critic capabilities."""
    from synthetic_india.engine import simulation

    # Verify critic_agent is imported
    assert hasattr(simulation, 'critic_agent')


def test_load_personas():
    personas = load_personas()
    assert len(personas) >= 5
    for p in personas:
        assert isinstance(p, PersonaProfile)
        assert p.name
        assert p.archetype


def test_build_demo_creatives():
    creatives = build_demo_creatives()
    assert len(creatives) == 2
    for c in creatives:
        assert isinstance(c, CreativeCard)
        assert c.brand
        assert c.headline


def test_cohort_selection():
    personas = load_personas()
    cohort = select_cohort(personas, "skincare")
    assert isinstance(cohort, list)
    assert len(cohort) > 0
    for p in cohort:
        assert isinstance(p, PersonaProfile)


def test_memory_stream_init():
    stream = MemoryStream("researcher_delhi_01")
    assert stream.size == 0


def test_memory_retriever_init():
    retriever = MemoryRetriever()
    assert retriever.config.recency_weight > 0
    assert retriever.config.relevance_weight > 0
    assert retriever.config.importance_weight > 0


def test_silver_persona_validation():
    personas = load_personas()
    for p in personas:
        persona, result = validate_persona(p.model_dump())
        assert result.passed, f"{p.persona_id} failed: {result.errors}"


def test_print_run_header_shows_brand_and_headline():
    """print_run_header should display brand, category, and headline."""
    creatives = build_demo_creatives()
    creative = creatives[0]  # Minimalist

    buf = StringIO()
    test_console = Console(file=buf, force_terminal=True)
    print_run_header(creatives=[creative], console=test_console)
    output = buf.getvalue()

    assert "Minimalist" in output
    assert "skincare" in output
    assert "Niacinamide" in output


def test_print_run_summary_shows_key_metrics():
    """print_run_summary should display run_id, cost, evaluation count."""
    meta = RunMetadata(
        run_id="test_run_001",
        brand="Minimalist",
        category="skincare",
        creative_ids=["c1"],
        persona_ids=["p1", "p2", "p3"],
        cohort_size=3,
        total_evaluations=3,
        total_cost_usd=0.0042,
        total_tokens=1500,
        status="completed",
        successful_evaluations=3,
    )

    buf = StringIO()
    test_console = Console(file=buf, force_terminal=True)
    print_run_summary(meta=meta, console=test_console)
    output = buf.getvalue()

    assert "test_run_001" in output
    assert "3" in output  # evaluations
    assert "0.0042" in output  # cost


def test_print_run_summary_shows_critic_stats():
    """print_run_summary should display critic quality gate stats when provided."""
    from synthetic_india.schemas.critic import CriticVerdict, CriticRunSummary

    meta = RunMetadata(
        run_id="test_run_002",
        brand="Minimalist",
        category="skincare",
        creative_ids=["c1"],
        persona_ids=["p1", "p2"],
        cohort_size=2,
        total_evaluations=2,
        total_cost_usd=0.01,
        total_tokens=3000,
        status="completed",
        successful_evaluations=2,
        quarantined_records=1,
    )

    verdicts = [
        CriticVerdict(
            evaluation_id="e1", persona_id="researcher_delhi_01",
            persona_consistency=8.0, sycophancy_score=2.0,
            cultural_authenticity=7.0, action_reasoning_alignment=9.0,
            explanation="Good.", flags=[], model_used="test", cost_usd=0.001,
        ),
        CriticVerdict(
            evaluation_id="e2", persona_id="skeptic_mumbai_01",
            persona_consistency=3.0, sycophancy_score=9.0,
            cultural_authenticity=4.0, action_reasoning_alignment=3.0,
            explanation="Bad.", flags=["sycophancy_detected"], model_used="test", cost_usd=0.001,
        ),
    ]
    critic_summary = CriticRunSummary.from_verdicts("test_run_002", verdicts)

    buf = StringIO()
    test_console = Console(file=buf, force_terminal=True)
    print_run_summary(meta=meta, critic_summary=critic_summary, console=test_console)
    output = buf.getvalue()

    assert "1" in output  # quarantined
    assert "50%" in output or "50" in output  # pass rate
