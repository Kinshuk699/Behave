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


# ── Vision-native evaluation tests ───────────────────────────


def test_creative_card_accepts_image_path():
    """CreativeCard should accept optional image_path field."""
    card_with = CreativeCard(
        creative_id="c_vision_01",
        brand="Minimalist",
        category="skincare",
        format="static_image",
        headline="10% Niacinamide Serum",
        image_path="/tmp/test_ad.png",
    )
    assert card_with.image_path == "/tmp/test_ad.png"

    card_without = CreativeCard(
        creative_id="c_vision_02",
        brand="Minimalist",
        category="skincare",
        format="static_image",
        headline="10% Niacinamide Serum",
    )
    assert card_without.image_path is None


def test_encode_image_returns_base64_and_media_type():
    """encode_image should return (base64_str, media_type) for a valid PNG."""
    import base64
    import tempfile
    from synthetic_india.agents.image_utils import encode_image

    # Create a minimal 1x1 red PNG (68 bytes)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_bytes)
        tmp_path = f.name

    b64_str, media_type = encode_image(tmp_path)

    assert media_type == "image/png"
    assert isinstance(b64_str, str)
    # Should be valid base64 that decodes back to original bytes
    decoded = base64.b64decode(b64_str)
    assert decoded == png_bytes

    import os
    os.unlink(tmp_path)


def test_encode_image_detects_jpeg():
    """encode_image should detect JPEG media type from extension."""
    import tempfile
    from synthetic_india.agents.image_utils import encode_image

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff\xe0fake_jpeg_data")
        tmp_path = f.name

    _, media_type = encode_image(tmp_path)
    assert media_type == "image/jpeg"

    import os
    os.unlink(tmp_path)


def test_call_anthropic_builds_vision_message():
    """call_anthropic should build multi-content message when image_base64 is provided."""
    from synthetic_india.agents.llm_client import _build_anthropic_messages

    # Text-only message
    msgs_text = _build_anthropic_messages(prompt="Evaluate this ad")
    assert len(msgs_text) == 1
    assert msgs_text[0]["role"] == "user"
    assert msgs_text[0]["content"] == "Evaluate this ad"

    # Vision message with image
    msgs_vision = _build_anthropic_messages(
        prompt="Evaluate this ad",
        image_base64="aWZha2VkYXRh",
        image_media_type="image/png",
    )
    assert len(msgs_vision) == 1
    content_blocks = msgs_vision[0]["content"]
    assert isinstance(content_blocks, list)
    assert len(content_blocks) == 2

    # First block should be the image
    assert content_blocks[0]["type"] == "image"
    assert content_blocks[0]["source"]["type"] == "base64"
    assert content_blocks[0]["source"]["data"] == "aWZha2VkYXRh"
    assert content_blocks[0]["source"]["media_type"] == "image/png"

    # Second block should be the text prompt
    assert content_blocks[1]["type"] == "text"
    assert content_blocks[1]["text"] == "Evaluate this ad"


def test_evaluator_prepares_vision_kwargs():
    """evaluate_creative should prepare image kwargs when creative has image_path."""
    import tempfile
    from synthetic_india.agents.persona_evaluator import _prepare_vision_kwargs

    # No image → empty dict
    card_no_image = CreativeCard(
        creative_id="c1", brand="Test", category="skincare", format="static_image",
    )
    kwargs = _prepare_vision_kwargs(card_no_image)
    assert kwargs == {}

    # With image → base64 + media_type
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_bytes)
        tmp_path = f.name

    card_with_image = CreativeCard(
        creative_id="c2", brand="Test", category="skincare", format="static_image",
        image_path=tmp_path,
    )
    kwargs = _prepare_vision_kwargs(card_with_image)
    assert "image_base64" in kwargs
    assert "image_media_type" in kwargs
    assert kwargs["image_media_type"] == "image/png"
    assert len(kwargs["image_base64"]) > 0

    import os
    os.unlink(tmp_path)


# ── Trend Follower persona tests ─────────────────────────────


def test_trend_follower_persona_loads():
    """Trend follower persona should load from disk and have correct archetype."""
    personas = load_personas()
    trend_followers = [p for p in personas if p.archetype == "trend_follower"]
    assert len(trend_followers) >= 1, "No trend_follower persona found"
    tf = trend_followers[0]
    assert tf.archetype == "trend_follower"
    assert tf.name
    assert tf.tagline
    assert tf.backstory
    assert tf.demographics.city
    # Key behavioral markers for trend follower
    assert tf.purchase_psychology.social_proof_need >= 0.8
    assert tf.media_behavior.influencer_trust >= 0.7
    assert tf.purchase_psychology.decision_speed == "fast"


def test_trend_follower_validates_silver():
    """Trend follower should pass silver-layer validation."""
    personas = load_personas()
    trend_followers = [p for p in personas if p.archetype == "trend_follower"]
    assert len(trend_followers) >= 1
    tf = trend_followers[0]
    persona, result = validate_persona(tf.model_dump())
    assert result.passed, f"trend_follower failed validation: {result.errors}"
