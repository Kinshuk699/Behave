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
    assert len(creatives) >= 2
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


# ── Memory Consumer tests ────────────────────────────────────


def test_memory_node_has_sequence_number():
    """MemoryNode should have a sequence_number field (Optional[int], default None)."""
    node = MemoryNode(
        node_id="mem_test_001",
        persona_id="researcher_delhi_01",
        memory_type="observation",
        description="Saw a Minimalist ad with niacinamide claims",
        subject="researcher_delhi_01",
        predicate="evaluated",
        object="Minimalist niacinamide serum",
        importance=6.0,
        category="skincare",
        brand="Minimalist",
    )
    assert hasattr(node, "sequence_number")
    assert node.sequence_number is None  # default

    node_with_seq = node.model_copy(update={"sequence_number": 42})
    assert node_with_seq.sequence_number == 42


def test_memory_config_has_consumer_fields():
    """MemoryConfig should have full_dump_threshold and include_cross_reflections."""
    from synthetic_india.config import MemoryConfig

    config = MemoryConfig()
    assert hasattr(config, "full_dump_threshold")
    assert config.full_dump_threshold == 50
    assert hasattr(config, "include_cross_reflections")
    assert config.include_cross_reflections is True  # default: cross-reflections ON


def test_memory_stream_assigns_sequence_numbers():
    """MemoryStream.add_node() should assign monotonic sequence_numbers."""
    stream = MemoryStream("test_persona")

    node1 = MemoryNode(
        node_id="mem_seq_01", persona_id="test_persona",
        memory_type="observation", description="First ad eval",
        subject="test_persona", predicate="evaluated", object="Brand A",
        importance=5.0, category="skincare", brand="Brand A",
    )
    node2 = MemoryNode(
        node_id="mem_seq_02", persona_id="test_persona",
        memory_type="observation", description="Second ad eval",
        subject="test_persona", predicate="evaluated", object="Brand B",
        importance=7.0, category="sports", brand="Brand B",
    )

    stream.add_node(node1)
    stream.add_node(node2)

    assert stream.nodes[0].sequence_number == 0
    assert stream.nodes[1].sequence_number == 1


def test_memory_consumer_consume_all_category_scoped():
    """consume_all should return only category-matched nodes + cross-category reflections."""
    from synthetic_india.memory.consumer import MemoryConsumer

    stream = MemoryStream("test_persona")

    # Add 3 skincare observations
    for i in range(3):
        stream.add_node(MemoryNode(
            node_id=f"mem_skin_{i}", persona_id="test_persona",
            memory_type="observation", description=f"Skincare eval {i}",
            subject="test_persona", predicate="evaluated", object=f"Brand {i}",
            importance=5.0, category="skincare", brand=f"Brand {i}",
        ))

    # Add 2 sports observations (should NOT appear in skincare consume_all)
    for i in range(2):
        stream.add_node(MemoryNode(
            node_id=f"mem_sport_{i}", persona_id="test_persona",
            memory_type="observation", description=f"Sports eval {i}",
            subject="test_persona", predicate="evaluated", object=f"SportBrand {i}",
            importance=5.0, category="sports", brand=f"SportBrand {i}",
        ))

    # Add 1 cross-category reflection (from sports, should appear in skincare consumption)
    stream.add_node(MemoryNode(
        node_id="ref_sports_01", persona_id="test_persona",
        memory_type="reflection", description="I distrust brands using urgency tactics",
        subject="test_persona", predicate="believes", object="urgency tactics",
        importance=8.0, category="sports",
    ))

    consumer = MemoryConsumer()
    result = consumer.consume_all(stream, category="skincare")

    # Should get 3 skincare obs + 1 cross-category reflection = 4
    assert len(result) == 4
    categories = [n.category for n in result]
    types = [n.memory_type for n in result]
    # All skincare nodes present
    assert categories.count("skincare") == 3
    # Cross-category reflection present
    assert "reflection" in [t.value if hasattr(t, 'value') else t for t in types]


def test_memory_consumer_consume_all_no_cross_reflections():
    """consume_all with include_cross_reflections=False should exclude cross-category reflections."""
    from synthetic_india.memory.consumer import MemoryConsumer
    from synthetic_india.config import MemoryConfig

    stream = MemoryStream("test_persona")

    stream.add_node(MemoryNode(
        node_id="mem_skin_0", persona_id="test_persona",
        memory_type="observation", description="Skincare eval",
        subject="test_persona", predicate="evaluated", object="Brand A",
        importance=5.0, category="skincare", brand="Brand A",
    ))
    stream.add_node(MemoryNode(
        node_id="ref_sports_01", persona_id="test_persona",
        memory_type="reflection", description="I distrust urgency tactics",
        subject="test_persona", predicate="believes", object="urgency tactics",
        importance=8.0, category="sports",
    ))

    config = MemoryConfig(include_cross_reflections=False)
    consumer = MemoryConsumer(config=config)
    result = consumer.consume_all(stream, category="skincare")

    # Only the skincare observation, no cross-category reflection
    assert len(result) == 1
    assert result[0].category == "skincare"


def test_memory_consumer_auto_selects_strategy():
    """consume() should auto-select full_dump for small streams, scored for large."""
    from synthetic_india.memory.consumer import MemoryConsumer
    from synthetic_india.config import MemoryConfig

    # Small stream (below threshold of 3)
    config = MemoryConfig(full_dump_threshold=3)
    consumer = MemoryConsumer(config=config)

    stream = MemoryStream("test_persona")
    for i in range(2):  # 2 skincare nodes < threshold of 3
        stream.add_node(MemoryNode(
            node_id=f"mem_{i}", persona_id="test_persona",
            memory_type="observation", description=f"Skincare eval {i}",
            subject="test_persona", predicate="evaluated", object=f"Brand {i}",
            importance=5.0, category="skincare", brand=f"Brand {i}",
        ))

    # Below threshold → should get ALL category nodes (full dump)
    result = consumer.consume(stream, query="skincare serum", category="skincare")
    assert len(result) == 2  # full dump of all 2 skincare nodes

    # Now add more to exceed threshold
    for i in range(2, 10):
        stream.add_node(MemoryNode(
            node_id=f"mem_{i}", persona_id="test_persona",
            memory_type="observation", description=f"Skincare eval {i}",
            subject="test_persona", predicate="evaluated", object=f"Brand {i}",
            importance=float(i), category="skincare", brand=f"Brand {i}",
        ))

    # 10 skincare nodes >= threshold of 3 → scored retrieval (top_k limits result)
    result = consumer.consume(stream, query="skincare serum", category="skincare", top_k=5)
    assert len(result) <= 5  # scored retrieval caps at top_k


def test_evaluator_imports_memory_consumer():
    """persona_evaluator should import and use MemoryConsumer instead of raw MemoryRetriever."""
    from synthetic_india.agents import persona_evaluator

    assert hasattr(persona_evaluator, 'MemoryConsumer')


def test_build_memory_block_accepts_memory_nodes():
    """_build_memory_block should accept list[MemoryNode] directly."""
    from synthetic_india.agents.persona_evaluator import _build_memory_block

    nodes = [
        MemoryNode(
            node_id="mem_block_01", persona_id="test_persona",
            memory_type="observation",
            description="Saw a Minimalist niacinamide ad, was impressed by transparency",
            subject="test_persona", predicate="evaluated", object="Minimalist",
            importance=6.0, category="skincare", brand="Minimalist",
        ),
        MemoryNode(
            node_id="ref_block_01", persona_id="test_persona",
            memory_type="reflection",
            description="I tend to distrust brands using urgency tactics",
            subject="test_persona", predicate="believes", object="urgency tactics",
            importance=8.0, category="sports",
        ),
    ]

    result = _build_memory_block(nodes)
    assert "Minimalist" in result
    assert "urgency" in result
    assert "Past Experiences" in result


# ── Memory Scope tests (per-persona scope toggle) ────────────


def test_memory_scope_enum_has_four_values():
    """MemoryScope should have NONE, CATEGORY, BRAND, FULL."""
    from synthetic_india.memory.consumer import MemoryScope

    assert MemoryScope.NONE == "none"
    assert MemoryScope.CATEGORY == "category"
    assert MemoryScope.BRAND == "brand"
    assert MemoryScope.FULL == "full"


def test_consume_scope_none_returns_empty():
    """Scope NONE should return no memories regardless of stream contents."""
    from synthetic_india.memory.consumer import MemoryConsumer, MemoryScope

    stream = MemoryStream("test_persona")
    stream.add_node(MemoryNode(
        node_id="mem_01", persona_id="test_persona",
        memory_type="observation", description="Saw a skincare ad",
        subject="test_persona", predicate="evaluated", object="Brand A",
        importance=5.0, category="skincare", brand="Brand A",
    ))

    consumer = MemoryConsumer()
    result = consumer.consume(
        stream=stream, query="skincare", category="skincare",
        scope=MemoryScope.NONE,
    )
    assert result == []


def test_consume_scope_category_filters_by_category():
    """Scope CATEGORY should return only same-category nodes (existing behavior)."""
    from synthetic_india.memory.consumer import MemoryConsumer, MemoryScope

    stream = MemoryStream("test_persona")
    stream.add_node(MemoryNode(
        node_id="mem_skin", persona_id="test_persona",
        memory_type="observation", description="Skincare eval",
        subject="test_persona", predicate="evaluated", object="Brand A",
        importance=5.0, category="skincare", brand="Brand A",
    ))
    stream.add_node(MemoryNode(
        node_id="mem_groc", persona_id="test_persona",
        memory_type="observation", description="Grocery eval",
        subject="test_persona", predicate="evaluated", object="Zepto",
        importance=5.0, category="grocery_delivery", brand="Zepto",
    ))

    consumer = MemoryConsumer()
    result = consumer.consume(
        stream=stream, query="skincare serum", category="skincare",
        scope=MemoryScope.CATEGORY,
    )
    assert len(result) == 1
    assert result[0].category == "skincare"


def test_consume_scope_brand_filters_by_brand():
    """Scope BRAND should return only memories from the same brand."""
    from synthetic_india.memory.consumer import MemoryConsumer, MemoryScope

    stream = MemoryStream("test_persona")
    stream.add_node(MemoryNode(
        node_id="mem_zepto1", persona_id="test_persona",
        memory_type="observation", description="Zepto grocery ad",
        subject="test_persona", predicate="evaluated", object="Zepto",
        importance=5.0, category="grocery_delivery", brand="Zepto",
    ))
    stream.add_node(MemoryNode(
        node_id="mem_zepto2", persona_id="test_persona",
        memory_type="observation", description="Zepto snacks ad",
        subject="test_persona", predicate="evaluated", object="Zepto",
        importance=6.0, category="grocery_delivery", brand="Zepto",
    ))
    stream.add_node(MemoryNode(
        node_id="mem_swiggy", persona_id="test_persona",
        memory_type="observation", description="Swiggy food ad",
        subject="test_persona", predicate="evaluated", object="Swiggy",
        importance=5.0, category="food_delivery", brand="Swiggy",
    ))

    consumer = MemoryConsumer()
    result = consumer.consume(
        stream=stream, query="Zepto grocery", category="grocery_delivery",
        scope=MemoryScope.BRAND, brand="Zepto",
    )
    assert len(result) == 2
    assert all(n.brand == "Zepto" for n in result)


def test_consume_scope_full_returns_everything():
    """Scope FULL should return all memories across all categories and brands."""
    from synthetic_india.memory.consumer import MemoryConsumer, MemoryScope

    stream = MemoryStream("test_persona")
    stream.add_node(MemoryNode(
        node_id="mem_skin", persona_id="test_persona",
        memory_type="observation", description="Skincare eval",
        subject="test_persona", predicate="evaluated", object="Brand A",
        importance=5.0, category="skincare", brand="Brand A",
    ))
    stream.add_node(MemoryNode(
        node_id="mem_groc", persona_id="test_persona",
        memory_type="observation", description="Grocery eval",
        subject="test_persona", predicate="evaluated", object="Zepto",
        importance=5.0, category="grocery_delivery", brand="Zepto",
    ))
    stream.add_node(MemoryNode(
        node_id="mem_food", persona_id="test_persona",
        memory_type="observation", description="Food delivery eval",
        subject="test_persona", predicate="evaluated", object="Swiggy",
        importance=5.0, category="food_delivery", brand="Swiggy",
    ))

    consumer = MemoryConsumer()
    result = consumer.consume(
        stream=stream, query="anything", category="skincare",
        scope=MemoryScope.FULL,
    )
    assert len(result) == 3


def test_get_exposure_summary():
    """get_exposure_summary() should report what a persona has been shown."""
    from synthetic_india.memory.consumer import MemoryConsumer

    stream = MemoryStream("test_persona")
    stream.add_node(MemoryNode(
        node_id="mem_01", persona_id="test_persona",
        memory_type="observation", description="Saw Zepto grocery ad",
        subject="test_persona", predicate="evaluated_pause",
        object="Zepto grocery_delivery creative",
        importance=5.0, category="grocery_delivery", brand="Zepto",
    ))
    stream.add_node(MemoryNode(
        node_id="mem_02", persona_id="test_persona",
        memory_type="observation", description="Saw Minimalist skincare ad",
        subject="test_persona", predicate="evaluated_engage",
        object="Minimalist skincare creative",
        importance=7.0, category="skincare", brand="Minimalist",
    ))

    consumer = MemoryConsumer()
    summary = consumer.get_exposure_summary(stream)

    assert summary["persona_id"] == "test_persona"
    assert summary["total_memories"] == 2
    assert "grocery_delivery" in summary["categories"]
    assert "skincare" in summary["categories"]
    assert "Zepto" in summary["brands"]
    assert "Minimalist" in summary["brands"]
    assert len(summary["exposures"]) == 2


def test_consume_default_scope_is_category():
    """Default scope (when not specified) should behave as CATEGORY — backwards compatible."""
    from synthetic_india.memory.consumer import MemoryConsumer

    stream = MemoryStream("test_persona")
    stream.add_node(MemoryNode(
        node_id="mem_skin", persona_id="test_persona",
        memory_type="observation", description="Skincare eval",
        subject="test_persona", predicate="evaluated", object="Brand A",
        importance=5.0, category="skincare", brand="Brand A",
    ))
    stream.add_node(MemoryNode(
        node_id="mem_groc", persona_id="test_persona",
        memory_type="observation", description="Grocery eval",
        subject="test_persona", predicate="evaluated", object="Zepto",
        importance=5.0, category="grocery_delivery", brand="Zepto",
    ))

    consumer = MemoryConsumer()
    # No scope param → should default to CATEGORY (backwards compatible)
    result = consumer.consume(stream=stream, query="skincare", category="skincare")
    assert len(result) == 1
    assert result[0].category == "skincare"


def test_evaluate_creative_accepts_memory_scope():
    """evaluate_creative() should accept memory_scope parameter."""
    import inspect
    from synthetic_india.agents.persona_evaluator import evaluate_creative

    sig = inspect.signature(evaluate_creative)
    assert "memory_scope" in sig.parameters, "evaluate_creative should accept memory_scope param"


def test_run_simulation_accepts_memory_scope():
    """run_simulation() should accept memory_scope parameter."""
    import inspect
    from synthetic_india.engine.simulation import run_simulation

    sig = inspect.signature(run_simulation)
    assert "memory_scope" in sig.parameters, "run_simulation should accept memory_scope param"


# ── Tiered model support tests ───────────────────────────────


def test_eval_model_is_configured():
    """Volume eval model should be set (Sonnet — user's API key only has Sonnet access)."""
    from synthetic_india.config import LLMConfig

    config = LLMConfig()
    assert "claude" in config.eval_model.lower(), (
        f"eval_model should be a Claude model, got {config.eval_model}"
    )


def test_reflection_model_exists():
    """LLMConfig should have a reflection_model field."""
    from synthetic_india.config import LLMConfig

    config = LLMConfig()
    assert hasattr(config, "reflection_model")
    assert "claude" in config.reflection_model.lower(), (
        f"reflection_model should be a Claude model, got {config.reflection_model}"
    )


def test_quality_models_stay_on_sonnet():
    """Critic, recommendation, and creative analysis should stay on Sonnet."""
    from synthetic_india.config import LLMConfig

    config = LLMConfig()
    assert "sonnet" in config.critic_model.lower()
    assert "sonnet" in config.recommendation_model.lower()
    assert "sonnet" in config.creative_analysis_model.lower()


def test_simulation_uses_reflection_model():
    """simulation module should use config.reflection_model for reflections, not eval_model."""
    import inspect
    from synthetic_india.engine import simulation

    source = inspect.getsource(simulation)
    assert "config.reflection_model" in source, (
        "simulation.py should use config.reflection_model for reflection calls"
    )


# ── India-specific CreativeCard fields (Feature #7) ──────────


def test_creative_card_has_festival_context():
    """CreativeCard should have an optional festival_context field."""
    card = CreativeCard(
        creative_id="test_fest",
        brand="TestBrand",
        category="skincare",
        format="static_image",
        festival_context="Diwali",
    )
    assert card.festival_context == "Diwali"

    # Default should be None
    card_default = CreativeCard(
        creative_id="test_default",
        brand="TestBrand",
        category="skincare",
        format="static_image",
    )
    assert card_default.festival_context is None


def test_creative_card_has_target_city_tier():
    """CreativeCard should have an optional target_city_tier field."""
    card = CreativeCard(
        creative_id="test_tier",
        brand="TestBrand",
        category="skincare",
        format="static_image",
        target_city_tier="Tier 2-3",
    )
    assert card.target_city_tier == "Tier 2-3"

    card_default = CreativeCard(
        creative_id="test_default",
        brand="TestBrand",
        category="skincare",
        format="static_image",
    )
    assert card_default.target_city_tier is None


def test_creative_card_has_cultural_references():
    """CreativeCard should have a cultural_references list field."""
    refs = ["rangoli motifs", "family gathering", "diyas"]
    card = CreativeCard(
        creative_id="test_culture",
        brand="TestBrand",
        category="skincare",
        format="static_image",
        cultural_references=refs,
    )
    assert card.cultural_references == refs

    card_default = CreativeCard(
        creative_id="test_default",
        brand="TestBrand",
        category="skincare",
        format="static_image",
    )
    assert card_default.cultural_references == []


def test_demo_creatives_include_diwali_ad():
    """build_demo_creatives should include a festival-themed Diwali ad."""
    demos = build_demo_creatives()
    diwali_ads = [c for c in demos if c.festival_context and "diwali" in c.festival_context.lower()]
    assert len(diwali_ads) >= 1, "Should have at least one Diwali demo creative"
    diwali = diwali_ads[0]
    assert diwali.cultural_references, "Diwali ad should have cultural_references"
    assert diwali.code_mixed is True, "Diwali ad should use Hinglish"


# ── Persona Library Expansion (Feature #8) ───────────────────


def test_persona_library_has_20_plus():
    """Persona library should have at least 20 personas."""
    personas = load_personas()
    assert len(personas) >= 20, f"Expected 20+ personas, got {len(personas)}"


def test_all_8_archetypes_populated():
    """Every archetype in the enum should have at least one persona JSON."""
    from synthetic_india.schemas.persona import Archetype

    personas = load_personas()
    archetypes_present = {p.archetype for p in personas}
    for arch in Archetype:
        assert arch.value in archetypes_present, f"Archetype '{arch.value}' has no persona JSON"


def test_all_personas_pass_silver_validation():
    """Every persona JSON must pass silver-layer validation."""
    personas = load_personas()
    for p in personas:
        persona, result = validate_persona(p.model_dump())
        assert result.passed, f"{p.persona_id} failed silver: {result.errors}"


def test_cohort_selection_with_large_pool():
    """Cohort selection should pick a diverse subset from 20+ personas for skincare."""
    personas = load_personas()
    cohort = select_cohort(personas, "skincare", cohort_size=8)
    assert len(cohort) >= 4, "Skincare cohort should have at least 4 personas"
    archetypes_in_cohort = {p.archetype for p in cohort}
    assert len(archetypes_in_cohort) >= 3, "Cohort should have at least 3 different archetypes"


# ── Databricks Medallion Pipeline (Feature #9) ───────────────


def test_bronze_prepare_personas_returns_flat_dicts():
    """prepare_personas_for_bronze should flatten PersonaProfiles into Delta-ready dicts."""
    from synthetic_india.pipeline.databricks_bronze import prepare_personas_for_bronze

    personas = load_personas()
    rows = prepare_personas_for_bronze(personas)

    assert len(rows) >= 20
    row = rows[0]
    # Must have top-level identity fields
    assert "persona_id" in row
    assert "name" in row
    assert "archetype" in row
    # Demographics should be flattened
    assert "city" in row
    assert "city_tier" in row
    assert "age" in row
    # Should have ingestion timestamp
    assert "_ingested_at" in row
    # No nested Pydantic objects — all values should be JSON-serializable primitives
    for key, val in row.items():
        assert not hasattr(val, "model_dump"), f"Field '{key}' is still a Pydantic model"


def test_bronze_prepare_creatives_returns_flat_dicts():
    """prepare_creatives_for_bronze should flatten CreativeCards into Delta-ready dicts."""
    from synthetic_india.pipeline.databricks_bronze import prepare_creatives_for_bronze

    creatives = build_demo_creatives()
    rows = prepare_creatives_for_bronze(creatives)

    assert len(rows) >= 2
    row = rows[0]
    assert "creative_id" in row
    assert "brand" in row
    assert "category" in row
    assert "headline" in row
    assert "_ingested_at" in row
    # Enum fields should be string values
    assert isinstance(row.get("format"), str)


def test_bronze_prepare_evaluations_returns_flat_dicts():
    """prepare_evaluations_for_bronze should flatten PersonaEvaluations into Delta-ready dicts."""
    from synthetic_india.pipeline.databricks_bronze import prepare_evaluations_for_bronze

    eval_data = PersonaEvaluation(
        evaluation_id="eval_db_001",
        run_id="run_db_test",
        creative_id="creative_test",
        persona_id="researcher_delhi_01",
        primary_action="read",
        sentiment="positive",
        overall_score=72.0,
        attention_score=7.0,
        relevance_score=8.0,
        trust_score=6.5,
        desire_score=5.0,
        clarity_score=8.0,
        first_impression="Clean product page",
        reasoning="Ingredients list is transparent.",
        objections=["Price seems high"],
        verbatim_reaction="Need to check reviews first.",
        importance_score=6.0,
        category="skincare",
        brand="Minimalist",
        key_themes=["transparency", "ingredients"],
    )

    rows = prepare_evaluations_for_bronze([eval_data])
    assert len(rows) == 1
    row = rows[0]
    assert row["evaluation_id"] == "eval_db_001"
    assert row["primary_action"] == "read"
    assert row["sentiment"] == "positive"
    assert "_ingested_at" in row
    # List fields should be JSON strings for Delta storage
    assert isinstance(row["objections"], str)
    assert isinstance(row["key_themes"], str)


def test_bronze_notebook_file_exists():
    """The bronze Databricks notebook should exist at notebooks/01_bronze_ingest.py."""
    from pathlib import Path
    notebook = Path(__file__).resolve().parents[1] / "notebooks" / "01_bronze_ingest.py"
    assert notebook.exists(), f"Bronze notebook not found at {notebook}"


def test_silver_validate_bronze_personas_all_pass():
    """Silver validation on properly-prepared bronze persona rows should pass all."""
    from synthetic_india.pipeline.databricks_silver import validate_persona_rows

    from synthetic_india.pipeline.databricks_bronze import prepare_personas_for_bronze
    personas = load_personas()
    bronze_rows = prepare_personas_for_bronze(personas)

    passed, quarantined = validate_persona_rows(bronze_rows)
    assert len(passed) >= 20
    assert len(quarantined) == 0


def test_silver_validate_bad_persona_quarantined():
    """A persona row with missing backstory should be quarantined."""
    from synthetic_india.pipeline.databricks_silver import validate_persona_rows

    bad_row = {
        "persona_id": "bad_persona_01",
        "name": "Bad Persona",
        "archetype": "researcher",
        "tagline": "Test",
        "backstory": "",  # Too short
        "city": "Delhi",
        "city_tier": "metro",
        "age": 25,
        "category_affinities": "[]",
        "_ingested_at": "2026-03-25T00:00:00",
    }
    passed, quarantined = validate_persona_rows([bad_row])
    assert len(passed) == 0
    assert len(quarantined) == 1
    assert "backstory" in quarantined[0]["errors"].lower()


def test_silver_validate_creative_rows():
    """Silver validation on demo creative rows should pass."""
    from synthetic_india.pipeline.databricks_silver import validate_creative_rows
    from synthetic_india.pipeline.databricks_bronze import prepare_creatives_for_bronze

    creatives = build_demo_creatives()
    bronze_rows = prepare_creatives_for_bronze(creatives)

    passed, quarantined = validate_creative_rows(bronze_rows)
    assert len(passed) >= 2
    assert len(quarantined) == 0


def test_silver_notebook_file_exists():
    """The silver Databricks notebook should exist at notebooks/02_silver_transform.py."""
    from pathlib import Path
    notebook = Path(__file__).resolve().parents[1] / "notebooks" / "02_silver_transform.py"
    assert notebook.exists(), f"Silver notebook not found at {notebook}"


def test_gold_build_scorecard_row():
    """build_scorecard_row should produce a flat dict from evaluation rows."""
    from synthetic_india.pipeline.databricks_gold import build_scorecard_row

    eval_rows = [
        {
            "evaluation_id": "e1", "creative_id": "c1", "persona_id": "p1",
            "run_id": "run_01", "brand": "Minimalist", "category": "skincare",
            "primary_action": "read", "sentiment": "positive",
            "overall_score": 72.0, "attention_score": 7.0, "relevance_score": 8.0,
            "trust_score": 6.5, "desire_score": 5.0, "clarity_score": 8.0,
        },
        {
            "evaluation_id": "e2", "creative_id": "c1", "persona_id": "p2",
            "run_id": "run_01", "brand": "Minimalist", "category": "skincare",
            "primary_action": "engage", "sentiment": "very_positive",
            "overall_score": 85.0, "attention_score": 9.0, "relevance_score": 8.5,
            "trust_score": 7.5, "desire_score": 8.0, "clarity_score": 9.0,
        },
    ]

    scorecard = build_scorecard_row("run_01", "c1", eval_rows)

    assert scorecard["run_id"] == "run_01"
    assert scorecard["creative_id"] == "c1"
    assert scorecard["brand"] == "Minimalist"
    assert scorecard["n_personas_evaluated"] == 2
    assert scorecard["avg_overall_score"] == 78.5  # (72 + 85) / 2
    assert scorecard["avg_attention"] == 8.0  # (7 + 9) / 2
    assert "read" in scorecard["action_distribution"]
    assert "positive" in scorecard["sentiment_distribution"]
    assert "_materialized_at" in scorecard


def test_gold_build_audit_row():
    """build_audit_row should produce a run audit dict."""
    from synthetic_india.pipeline.databricks_gold import build_audit_row

    audit = build_audit_row(
        run_id="run_01",
        brand="Minimalist",
        category="skincare",
        n_creatives=3,
        n_evaluations=15,
        n_passed=13,
        n_quarantined=2,
    )

    assert audit["run_id"] == "run_01"
    assert audit["n_creatives"] == 3
    assert audit["total_evaluations"] == 15
    assert audit["quarantined_records"] == 2
    assert "_materialized_at" in audit


def test_gold_notebook_file_exists():
    """The gold Databricks notebook should exist at notebooks/03_gold_materialize.py."""
    from pathlib import Path
    notebook = Path(__file__).resolve().parents[1] / "notebooks" / "03_gold_materialize.py"
    assert notebook.exists(), f"Gold notebook not found at {notebook}"


# ── Simulation Ingest Pipeline (Feature #11) ──────────────────


def test_ingest_notebook_file_exists():
    """The simulation ingest notebook should exist at notebooks/04_simulation_ingest.py."""
    from pathlib import Path
    notebook = Path(__file__).resolve().parents[1] / "notebooks" / "04_simulation_ingest.py"
    assert notebook.exists(), f"Simulation ingest notebook not found at {notebook}"


def test_bronze_prepare_evaluations_from_run_json():
    """Bronze prepare should handle real evaluation JSON from a simulation run."""
    import json
    from pathlib import Path

    run_dir = Path(__file__).resolve().parents[1] / "data" / "runs" / "run_e3d656cc826e"
    if not run_dir.exists():
        import pytest
        pytest.skip("No real run data yet")

    raw_evals = json.loads((run_dir / "evaluations.json").read_text())
    assert len(raw_evals) >= 1

    # Each evaluation should have the key fields the silver layer validates
    for e in raw_evals:
        assert e.get("evaluation_id"), "evaluation_id must be present"
        assert len(e.get("reasoning", "")) >= 10, "reasoning must be substantial"
        assert len(e.get("verbatim_reaction", "")) >= 5, "verbatim must be present"


def test_silver_validates_real_evaluation_rows():
    """Silver validation should pass real (high-quality) evaluation data."""
    import json
    from pathlib import Path
    from synthetic_india.pipeline.databricks_silver import validate_evaluation_rows

    run_dir = Path(__file__).resolve().parents[1] / "data" / "runs" / "run_e3d656cc826e"
    if not run_dir.exists():
        import pytest
        pytest.skip("No real run data yet")

    raw_evals = json.loads((run_dir / "evaluations.json").read_text())
    passed, quarantined = validate_evaluation_rows(raw_evals)

    assert len(passed) >= 1, "At least one evaluation should pass validation"
    assert len(quarantined) == 0, f"Real evals should not be quarantined: {quarantined}"


def test_gold_scorecard_from_real_evals():
    """Gold scorecard should produce valid aggregates from real evaluation data."""
    import json
    from pathlib import Path
    from synthetic_india.pipeline.databricks_gold import build_scorecard_row

    run_dir = Path(__file__).resolve().parents[1] / "data" / "runs" / "run_e3d656cc826e"
    if not run_dir.exists():
        import pytest
        pytest.skip("No real run data yet")

    raw_evals = json.loads((run_dir / "evaluations.json").read_text())
    scorecard = build_scorecard_row("run_e3d656cc826e", "zepto_ad_01", raw_evals)

    assert scorecard["n_personas_evaluated"] == len(raw_evals)
    assert 0 <= scorecard["avg_overall_score"] <= 100
    assert scorecard["avg_attention"] > 0
    assert scorecard["run_id"] == "run_e3d656cc826e"
    assert "_materialized_at" in scorecard


# ── MLflow integration tests ─────────────────────────────────


def test_ingest_notebook_uses_mlflow():
    """04_simulation_ingest.py should contain MLflow logging."""
    from pathlib import Path

    notebook = Path(__file__).resolve().parents[1] / "notebooks" / "04_simulation_ingest.py"
    content = notebook.read_text()
    assert "mlflow" in content, "Ingest notebook should use MLflow for experiment tracking"
    assert "mlflow.log_param" in content or "mlflow.log_params" in content, \
        "Notebook should log params to MLflow"
    assert "mlflow.log_metric" in content or "mlflow.log_metrics" in content, \
        "Notebook should log metrics to MLflow"


def test_build_mlflow_payload_from_run_data():
    """Pipeline helper should build MLflow-ready params + metrics from run metadata and scorecards."""
    from synthetic_india.pipeline.mlflow_utils import build_mlflow_payload

    metadata = {
        "run_id": "run_abc123",
        "brand": "Zepto",
        "category": "grocery_delivery",
        "cohort_size": 5,
        "total_evaluations": 5,
        "successful_evaluations": 5,
        "quarantined_records": 0,
        "total_cost_usd": 0.12,
        "total_tokens": 16000,
    }
    scorecard = {
        "avg_overall_score": 42.4,
        "avg_attention": 4.2,
        "avg_relevance": 5.0,
        "avg_trust": 6.1,
        "avg_desire": 3.5,
        "avg_clarity": 6.8,
        "n_personas_evaluated": 5,
    }

    payload = build_mlflow_payload(metadata, scorecard)

    # Params
    assert payload["params"]["run_id"] == "run_abc123"
    assert payload["params"]["brand"] == "Zepto"
    assert payload["params"]["category"] == "grocery_delivery"

    # Metrics
    assert payload["metrics"]["avg_overall_score"] == 42.4
    assert payload["metrics"]["total_cost_usd"] == 0.12
    assert payload["metrics"]["total_tokens"] == 16000
    assert payload["metrics"]["n_personas_evaluated"] == 5
    assert payload["metrics"]["quarantine_rate"] == 0.0


# ── Dashboard tests ──────────────────────────────────────────


def test_dashboard_app_exists():
    """dashboard/app.py should exist."""
    from pathlib import Path

    app_file = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    assert app_file.exists(), "dashboard/app.py not found"


def test_dashboard_static_files_exist():
    """Dashboard static assets must exist."""
    from pathlib import Path

    static = Path(__file__).resolve().parents[1] / "dashboard" / "static"
    for name in ("index.html", "styles.css", "app.js"):
        assert (static / name).exists(), f"dashboard/static/{name} not found"


def test_dashboard_has_preloaded_data():
    """index.html should embed the Zepto run data for instant display."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "dashboard" / "static" / "index.html").read_text()
    assert "run_e3d656cc826e" in html, "Pre-loaded run ID should be in HTML"
    assert "Zepto" in html, "Pre-loaded brand should be in HTML"
    assert "42.4" in html or "42.4" in html, "Pre-loaded overall score should be in HTML"


def test_dashboard_health_endpoint():
    """GET /api/health should return 200."""
    import sys
    from pathlib import Path

    # Import the FastAPI app
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
    from starlette.testclient import TestClient

    from app import app

    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_dashboard_simulate_rejects_bad_password():
    """POST /api/simulate without correct password returns 403."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
    from starlette.testclient import TestClient

    from app import app

    client = TestClient(app)
    resp = client.post("/api/simulate", json={"password": "wrong", "brand": "Test", "category": "test"})
    assert resp.status_code == 403


def test_dashboard_render_config_exists():
    """render.yaml deployment config should exist."""
    from pathlib import Path

    render_yaml = Path(__file__).resolve().parents[1] / "dashboard" / "render.yaml"
    assert render_yaml.exists(), "dashboard/render.yaml not found"


# ── Auto-ingest to Databricks tests ──────────────────────────


def test_databricks_ingest_module_exists():
    """The databricks_ingest module should be importable."""
    from synthetic_india.pipeline import databricks_ingest
    assert hasattr(databricks_ingest, "auto_ingest")
    assert hasattr(databricks_ingest, "upload_run_files")
    assert hasattr(databricks_ingest, "trigger_ingest_notebook")


def test_databricks_ingest_workspace_path():
    """upload_run_files should construct the correct workspace path."""
    from synthetic_india.pipeline.databricks_ingest import _workspace_run_path, _dbfs_run_path
    ws_path = _workspace_run_path("run_abc123")
    assert "data/runs/run_abc123" in ws_path
    assert ws_path.startswith("/Workspace/")
    dbfs_path = _dbfs_run_path("run_abc123")
    assert "run_abc123" in dbfs_path
    assert dbfs_path.startswith("/synthetic_india/")


def test_databricks_ingest_notebook_path():
    """trigger_ingest_notebook should target the correct notebook."""
    from synthetic_india.pipeline.databricks_ingest import NOTEBOOK_PATH
    assert "04_simulation_ingest" in NOTEBOOK_PATH
    assert NOTEBOOK_PATH.startswith("/Workspace/")


def test_databricks_ingest_graceful_without_sdk():
    """auto_ingest should not crash if databricks-sdk is not installed."""
    from pathlib import Path
    from unittest.mock import patch
    from synthetic_india.pipeline.databricks_ingest import auto_ingest

    # Simulate SDK import failure
    with patch("synthetic_india.pipeline.databricks_ingest._get_client", side_effect=ImportError("no sdk")):
        # Should not raise — just logs a warning
        result = auto_ingest("run_fake", Path("/tmp/fake"))
        assert result is False


# ── Memory → Databricks wiring tests ─────────────────────────


def test_run_metadata_has_memory_scope():
    """RunMetadata should have an optional memory_scope field."""
    meta_with = RunMetadata(
        run_id="test_ms", brand="Zepto", category="grocery_delivery",
        creative_ids=["c1"], persona_ids=["p1"], cohort_size=1,
        total_evaluations=1, memory_scope="category",
    )
    assert meta_with.memory_scope == "category"

    meta_without = RunMetadata(
        run_id="test_ms2", brand="Zepto", category="grocery_delivery",
        creative_ids=["c1"], persona_ids=["p1"], cohort_size=1,
        total_evaluations=1,
    )
    assert meta_without.memory_scope is None


def test_save_run_creates_memory_nodes_json(tmp_path):
    """_save_run should create memory_nodes.json when new_memory_nodes is provided."""
    import json
    from unittest.mock import patch
    from synthetic_india.engine.simulation import _save_run

    meta = RunMetadata(
        run_id="test_mem_nodes", brand="Zepto", category="grocery_delivery",
        creative_ids=["c1"], persona_ids=["p1"], cohort_size=1,
        total_evaluations=1, memory_scope="category",
    )
    nodes = [
        MemoryNode(
            node_id="mem_test_01", persona_id="test_persona",
            memory_type="observation", description="Saw a Zepto ad",
            subject="test_persona", predicate="evaluated_pause",
            object="Zepto grocery creative", importance=5.0,
            category="grocery_delivery", brand="Zepto",
        ),
    ]

    # Patch RUNS_DIR to tmp_path to avoid polluting real data
    with patch("synthetic_india.engine.simulation.RUNS_DIR", tmp_path):
        # Also patch auto_ingest to avoid Databricks call
        with patch("synthetic_india.pipeline.databricks_ingest.auto_ingest", return_value=False):
            _save_run(meta, [], [], None, None, new_memory_nodes=nodes)

    run_dir = tmp_path / "test_mem_nodes"
    assert (run_dir / "memory_nodes.json").exists()

    saved_nodes = json.loads((run_dir / "memory_nodes.json").read_text())
    assert len(saved_nodes) == 1
    assert saved_nodes[0]["node_id"] == "mem_test_01"
    assert saved_nodes[0]["brand"] == "Zepto"


def test_memory_nodes_in_run_files():
    """memory_nodes.json must be in the RUN_FILES list for Databricks upload."""
    from synthetic_india.pipeline.databricks_ingest import RUN_FILES
    assert "memory_nodes.json" in RUN_FILES


def test_backfill_memory_files_collects_nodes(tmp_path):
    """backfill_memory_files should read local memory JSONs and return all nodes."""
    import json
    from synthetic_india.pipeline.databricks_ingest import backfill_memory_files

    # Create a fake memory directory with one file containing 2 nodes
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    (mem_dir / "test_persona_memory.json").write_text(json.dumps({
        "persona_id": "test_persona",
        "nodes": [
            {"node_id": "n1", "persona_id": "test_persona", "description": "First memory", "importance": 3.0},
            {"node_id": "n2", "persona_id": "test_persona", "description": "Second memory", "importance": 5.0},
        ]
    }))

    nodes = backfill_memory_files(memory_dir=mem_dir, upload=False)
    assert len(nodes) == 2
    assert nodes[0]["node_id"] == "n1"
    assert nodes[1]["node_id"] == "n2"


def test_databricks_reader_read_personas_fallback():
    """read_personas should fall back to local files when Databricks is unavailable."""
    from synthetic_india.pipeline.databricks_reader import read_personas

    # Without Databricks SDK installed or configured, should fall back to local
    personas = read_personas()
    # We have 20 persona files locally
    assert len(personas) >= 10  # At least our known personas
    assert all(hasattr(p, "persona_id") for p in personas)


def test_databricks_reader_read_memory_nodes_fallback():
    """read_memory_nodes should fall back to local files when Databricks is unavailable."""
    from synthetic_india.pipeline.databricks_reader import read_memory_nodes

    nodes = read_memory_nodes(persona_id="aspirational_buyer_hyderabad_01")
    # This persona has 2 nodes in local data/memory/
    assert len(nodes) >= 1
    assert all(hasattr(n, "node_id") for n in nodes)


def test_load_personas_uses_reader():
    """load_personas should delegate to databricks_reader.read_personas."""
    from unittest.mock import patch, MagicMock
    from synthetic_india.engine.simulation import load_personas
    from synthetic_india.schemas.persona import PersonaProfile

    # Mock the reader to return a known list
    fake_persona = MagicMock(spec=PersonaProfile)
    fake_persona.persona_id = "test_persona"

    with patch(
        "synthetic_india.engine.simulation._read_personas_with_fallback",
        return_value=[fake_persona],
    ) as mock_read:
        result = load_personas()
        mock_read.assert_called_once()
        assert len(result) == 1
        assert result[0].persona_id == "test_persona"


# ── Deep Persona Overhaul (2026-03-28) ───────────────────────


def test_generational_touchstones_model():
    """GenerationalTouchstones should validate with era, ads, cultural refs, nostalgia, brands."""
    from synthetic_india.schemas.persona import GenerationalTouchstones

    gt = GenerationalTouchstones(
        formative_era="90s Doordarshan kid",
        iconic_ads=["Nirma washing powder", "Cadbury Kuch Meetha Ho Jaaye"],
        cultural_references=["Buniyaad on DD", "India winning 1983 World Cup"],
        nostalgia_intensity=0.85,
        formative_brands=["Nirma", "Amul", "Tata Tea"],
    )
    assert gt.formative_era == "90s Doordarshan kid"
    assert gt.nostalgia_intensity == 0.85
    assert len(gt.iconic_ads) == 2


def test_internal_conflict_model():
    """InternalConflict should capture tension + resolution tendency."""
    from synthetic_india.schemas.persona import InternalConflict

    ic = InternalConflict(
        tension="Wants premium brands but flat EMI eats into budget",
        resolution_tendency="Splurges on small luxuries, saves on big tickets",
    )
    assert "premium" in ic.tension
    assert "small luxuries" in ic.resolution_tendency


def test_brand_relationship_model():
    """BrandRelationship should capture brand, relationship type, emotional history, intensity."""
    from synthetic_india.schemas.persona import BrandRelationship

    br = BrandRelationship(
        brand="Tata Tea",
        relationship_type="nostalgic_friend",
        emotional_history="Dad always bought Tata Tea. It's not a choice, it's identity.",
        intensity=0.95,
    )
    assert br.brand == "Tata Tea"
    assert br.relationship_type == "nostalgic_friend"
    assert br.intensity == 0.95


def test_influencer_model():
    """Influencer should capture role, strength, domain."""
    from synthetic_india.schemas.persona import Influencer

    inf = Influencer(
        role="mother",
        influence_strength=0.9,
        influence_domain="grocery, household",
    )
    assert inf.role == "mother"
    assert inf.influence_strength == 0.9


def test_persona_new_fields_are_optional():
    """PersonaProfile should still load existing JSON without new fields (backward compat)."""
    personas = load_personas()
    # At least one persona should load without error even if new fields are absent
    assert len(personas) >= 20
    for p in personas:
        # New fields should have defaults (None or empty list)
        assert hasattr(p, "generational_touchstones")
        assert hasattr(p, "internal_conflicts")
        assert hasattr(p, "influence_network")
        assert hasattr(p, "values_hierarchy")
        assert hasattr(p, "cognitive_biases")


def test_persona_with_all_new_fields():
    """PersonaProfile should accept all new fields when provided."""
    from synthetic_india.schemas.persona import (
        GenerationalTouchstones, InternalConflict, BrandRelationship, Influencer,
    )

    # Load a base persona and add new fields
    personas = load_personas()
    base = personas[0].model_dump()
    base["generational_touchstones"] = {
        "formative_era": "Jio-era digital native",
        "iconic_ads": ["Jio Dhan Dhana Dhan", "CRED ads"],
        "cultural_references": ["IPL since childhood", "COVID lockdown in college"],
        "nostalgia_intensity": 0.3,
        "formative_brands": ["Flipkart", "Swiggy"],
    }
    base["internal_conflicts"] = [
        {"tension": "FOMO vs budget reality", "resolution_tendency": "Buys and returns within 7 days"},
    ]
    base["influence_network"] = [
        {"role": "college_friends", "influence_strength": 0.8, "influence_domain": "tech, fashion"},
    ]
    base["values_hierarchy"] = ["self_expression", "convenience", "value_for_money"]
    base["cognitive_biases"] = ["present_bias", "bandwagon_effect"]

    enriched = PersonaProfile(**base)
    assert enriched.generational_touchstones is not None
    assert enriched.generational_touchstones.formative_era == "Jio-era digital native"
    assert len(enriched.internal_conflicts) == 1
    assert len(enriched.influence_network) == 1
    assert enriched.values_hierarchy[0] == "self_expression"
    assert "present_bias" in enriched.cognitive_biases


def test_category_affinity_brand_relationships():
    """CategoryAffinity should accept optional brand_relationships."""
    from synthetic_india.schemas.persona import CategoryAffinity, BrandRelationship

    ca = CategoryAffinity(
        category="grocery",
        interest_level=0.85,
        monthly_spend_inr=15000,
        preferred_brands=["Tata", "Amul"],
        purchase_frequency="weekly",
        brand_relationships=[
            BrandRelationship(
                brand="Tata",
                relationship_type="loyal_lover",
                emotional_history="Three generations of Tata Tea in our house.",
                intensity=0.95,
            ),
            BrandRelationship(
                brand="Patanjali",
                relationship_type="burned_ex",
                emotional_history="Tried it because of Baba Ramdev hype. Quality was inconsistent.",
                intensity=0.4,
            ),
        ],
    )
    assert len(ca.brand_relationships) == 2
    assert ca.brand_relationships[0].relationship_type == "loyal_lover"
    assert ca.brand_relationships[1].relationship_type == "burned_ex"


def test_nostalgia_intensity_bounds():
    """nostalgia_intensity should be bounded 0-1."""
    from synthetic_india.schemas.persona import GenerationalTouchstones
    import pydantic

    # Valid
    gt = GenerationalTouchstones(
        formative_era="test", iconic_ads=[], cultural_references=[],
        nostalgia_intensity=0.5, formative_brands=[],
    )
    assert gt.nostalgia_intensity == 0.5

    # Invalid — above 1
    try:
        GenerationalTouchstones(
            formative_era="test", iconic_ads=[], cultural_references=[],
            nostalgia_intensity=1.5, formative_brands=[],
        )
        assert False, "Should have raised validation error"
    except pydantic.ValidationError:
        pass


def test_influence_strength_bounds():
    """influence_strength should be bounded 0-1."""
    from synthetic_india.schemas.persona import Influencer
    import pydantic

    # Valid
    inf = Influencer(role="spouse", influence_strength=0.7, influence_domain="all")
    assert inf.influence_strength == 0.7

    # Invalid
    try:
        Influencer(role="spouse", influence_strength=1.5, influence_domain="all")
        assert False, "Should have raised validation error"
    except pydantic.ValidationError:
        pass


# ── Phase 3a: Evaluator prompt rendering tests ─────────────────


def _load_enriched_persona():
    """Helper: load a known enriched persona for prompt rendering tests."""
    personas = load_personas()
    # Find impulse_buyer_delhi_01 — we know it's fully enriched
    for p in personas:
        if p.persona_id == "impulse_buyer_delhi_01":
            return p
    raise RuntimeError("impulse_buyer_delhi_01 not found")


def test_persona_block_renders_generational_touchstones():
    """_build_persona_block should render generational_touchstones when present."""
    from synthetic_india.agents.persona_evaluator import _build_persona_block

    persona = _load_enriched_persona()
    block = _build_persona_block(persona)

    assert "Cultural Memory" in block or "Generational" in block
    assert persona.generational_touchstones.formative_era in block
    # At least one iconic ad should appear
    assert persona.generational_touchstones.iconic_ads[0] in block
    assert "nostalgia" in block.lower() or "nostalgia_intensity" in block


def test_persona_block_renders_internal_conflicts():
    """_build_persona_block should render internal_conflicts when present."""
    from synthetic_india.agents.persona_evaluator import _build_persona_block

    persona = _load_enriched_persona()
    block = _build_persona_block(persona)

    assert "Tension" in block or "Conflict" in block or "Inner" in block
    # First conflict's tension text should appear
    assert persona.internal_conflicts[0].tension in block


def test_persona_block_renders_influence_network():
    """_build_persona_block should render influence_network when present."""
    from synthetic_india.agents.persona_evaluator import _build_persona_block

    persona = _load_enriched_persona()
    block = _build_persona_block(persona)

    assert "Influence" in block
    # First influencer's role should appear
    assert persona.influence_network[0].role in block


def test_persona_block_renders_values_hierarchy():
    """_build_persona_block should render values_hierarchy when present."""
    from synthetic_india.agents.persona_evaluator import _build_persona_block

    persona = _load_enriched_persona()
    block = _build_persona_block(persona)

    assert "Values" in block
    assert persona.values_hierarchy[0] in block


def test_persona_block_renders_cognitive_biases():
    """_build_persona_block should render cognitive_biases when present."""
    from synthetic_india.agents.persona_evaluator import _build_persona_block

    persona = _load_enriched_persona()
    block = _build_persona_block(persona)

    assert "Cognitive" in block or "Biases" in block
    assert persona.cognitive_biases[0] in block


def test_persona_block_renders_brand_relationships():
    """_build_persona_block should render brand_relationships within category affinities."""
    from synthetic_india.agents.persona_evaluator import _build_persona_block

    persona = _load_enriched_persona()
    block = _build_persona_block(persona)

    # The enriched persona has brand_relationships on category affinities
    first_cat = persona.category_affinities[0]
    if first_cat.brand_relationships:
        br = first_cat.brand_relationships[0]
        assert br.brand in block
        assert br.relationship_type in block


def test_persona_block_omits_missing_deep_fields():
    """_build_persona_block should gracefully omit deep fields when they are None/empty."""
    from synthetic_india.agents.persona_evaluator import _build_persona_block

    persona = _load_enriched_persona()
    # Create a copy without deep fields
    data = persona.model_dump()
    data["generational_touchstones"] = None
    data["internal_conflicts"] = []
    data["influence_network"] = []
    data["values_hierarchy"] = []
    data["cognitive_biases"] = []
    for aff in data["category_affinities"]:
        aff["brand_relationships"] = []
    stripped = PersonaProfile(**data)

    block = _build_persona_block(stripped)

    # Should still have core sections
    assert "Who You Are" in block
    assert "Purchase Psychology" in block
    # Should NOT have deep sections
    assert "Cultural Memory" not in block
    assert "Inner Tensions" not in block


def test_evaluator_system_mentions_real_voice():
    """EVALUATOR_SYSTEM should instruct authentic consumer voice, not focus-group speak."""
    from synthetic_india.agents.persona_evaluator import EVALUATOR_SYSTEM

    lower = EVALUATOR_SYSTEM.lower()
    assert "whatsapp" in lower or "voice note" in lower or "real person" in lower
    assert "focus group" in lower or "marketing consultant" in lower


# ── Phase 3b: Critic prompt rendering tests ─────────────────────


def _make_test_evaluation(persona_id: str) -> PersonaEvaluation:
    """Helper: build a minimal PersonaEvaluation for critic prompt tests."""
    return PersonaEvaluation(
        evaluation_id="eval_critic_test",
        run_id="run_test",
        creative_id="creative_test",
        persona_id=persona_id,
        primary_action="read",
        sentiment="positive",
        overall_score=72.0,
        attention_score=7.0,
        relevance_score=8.0,
        trust_score=6.5,
        desire_score=5.0,
        clarity_score=8.0,
        first_impression="Looks clean",
        reasoning="Transparent ingredients",
        objections=["Price seems high"],
        what_would_change_mind="Clinical data",
        verbatim_reaction="Let me check reviews first.",
        importance_score=6.0,
        category="skincare",
        brand="Minimalist",
        key_themes=["transparency"],
    )


def test_critic_prompt_includes_all_purchase_psychology():
    """Critic prompt should include all 8 purchase_psychology floats, not just 3."""
    from synthetic_india.agents.critic_agent import build_critic_prompt

    persona = _load_enriched_persona()
    evaluation = _make_test_evaluation(persona.persona_id)
    _, prompt = build_critic_prompt(persona=persona, evaluation=evaluation)

    # Should include all 8 fields
    assert "social_proof_need" in prompt or "social proof" in prompt.lower()
    assert "risk_tolerance" in prompt or "risk tolerance" in prompt.lower()
    assert "deal_sensitivity" in prompt or "deal sensitivity" in prompt.lower()
    assert "decision_speed" in prompt or "decision speed" in prompt.lower()


def test_critic_prompt_includes_backstory():
    """Critic prompt should include backstory and current_life_context."""
    from synthetic_india.agents.critic_agent import build_critic_prompt

    persona = _load_enriched_persona()
    evaluation = _make_test_evaluation(persona.persona_id)
    _, prompt = build_critic_prompt(persona=persona, evaluation=evaluation)

    assert persona.backstory[:50] in prompt
    assert persona.current_life_context[:50] in prompt


def test_critic_prompt_includes_deep_fields():
    """Critic prompt should include generational_touchstones, internal_conflicts, values, biases."""
    from synthetic_india.agents.critic_agent import build_critic_prompt

    persona = _load_enriched_persona()
    evaluation = _make_test_evaluation(persona.persona_id)
    _, prompt = build_critic_prompt(persona=persona, evaluation=evaluation)

    # Generational touchstones
    assert persona.generational_touchstones.formative_era[:30] in prompt
    # Internal conflicts — first tension
    assert persona.internal_conflicts[0].tension[:30] in prompt
    # Values hierarchy
    assert persona.values_hierarchy[0] in prompt
    # Cognitive biases
    assert persona.cognitive_biases[0] in prompt


def test_critic_prompt_generational_consistency_check():
    """Critic prompt should instruct checking for generational anachronisms."""
    from synthetic_india.agents.critic_agent import build_critic_prompt

    persona = _load_enriched_persona()
    evaluation = _make_test_evaluation(persona.persona_id)
    _, prompt = build_critic_prompt(persona=persona, evaluation=evaluation)

    lower = prompt.lower()
    assert "generational" in lower or "anachronis" in lower or "age-appropriate" in lower


# ── Phase 4: Memory system tests ──────────────────────────────


def test_reflection_threshold_lowered():
    """MemoryConfig.reflection_threshold should be 50, not 150."""
    from synthetic_india.config import MemoryConfig

    config = MemoryConfig()
    assert config.reflection_threshold == 50.0


def test_memory_stream_default_reflection_threshold():
    """MemoryStream default threshold should match the lowered config value."""
    stream = MemoryStream(persona_id="test_persona")
    assert stream.reflection_threshold == 50.0


def test_add_preference_memory():
    """MemoryStream.add_preference_memory should create PREFERENCE nodes."""
    from synthetic_india.schemas.memory import MemoryType

    stream = MemoryStream(persona_id="test_persona")
    node = stream.add_preference_memory(
        brand="Minimalist",
        category="skincare",
        description="I really like Minimalist's transparent ingredient lists.",
        importance=7.5,
        source_evaluation_id="eval_001",
    )

    assert node.memory_type == MemoryType.PREFERENCE
    assert node.brand == "Minimalist"
    assert node.category == "skincare"
    assert node.importance == 7.5
    assert stream.size == 1


def test_add_category_belief_memory():
    """MemoryStream.add_category_belief_memory should create CATEGORY_BELIEF nodes."""
    from synthetic_india.schemas.memory import MemoryType

    stream = MemoryStream(persona_id="test_persona")
    node = stream.add_category_belief_memory(
        category="skincare",
        description="Skincare brands relying on celebrity endorsements are usually overpriced.",
        importance=8.0,
        source_evaluation_id="eval_002",
    )

    assert node.memory_type == MemoryType.CATEGORY_BELIEF
    assert node.category == "skincare"
    assert node.importance == 8.0
    assert stream.size == 1


def test_should_reflect_at_threshold_50():
    """should_reflect should trigger after cumulative importance >= 50."""
    from synthetic_india.schemas.memory import MemoryType

    stream = MemoryStream(persona_id="test_persona")

    # Add nodes with importance summing to 49 — should not trigger
    for i in range(7):
        node = MemoryNode(
            node_id=f"mem_{i}",
            persona_id="test_persona",
            memory_type=MemoryType.OBSERVATION,
            description=f"Observation {i}",
            subject="test",
            predicate="evaluated",
            object="test creative",
            importance=7.0,
        )
        stream.add_node(node)

    assert stream._importance_since_reflection == 49.0
    assert not stream.should_reflect

    # One more node pushes over 50
    node = MemoryNode(
        node_id="mem_final",
        persona_id="test_persona",
        memory_type=MemoryType.OBSERVATION,
        description="Final observation",
        subject="test",
        predicate="evaluated",
        object="test creative",
        importance=2.0,
    )
    stream.add_node(node)
    assert stream._importance_since_reflection == 51.0
    assert stream.should_reflect


# ── Preference/belief wiring tests ─────────────────────────────


def test_high_score_creates_preference_memory():
    """Evaluations with overall_score > 70 should create a PREFERENCE memory node."""
    from synthetic_india.engine.simulation import maybe_create_preference_or_belief
    from synthetic_india.schemas.memory import MemoryType

    stream = MemoryStream(persona_id="test_persona")
    evaluation = PersonaEvaluation(
        evaluation_id="eval_high",
        run_id="run_test",
        creative_id="creative_test",
        persona_id="test_persona",
        primary_action="click",
        sentiment="very_positive",
        overall_score=85.0,
        attention_score=8.0,
        relevance_score=9.0,
        trust_score=8.0,
        desire_score=8.5,
        clarity_score=9.0,
        first_impression="Love it",
        reasoning="Great product, fits my needs perfectly.",
        objections=[],
        verbatim_reaction="Yeh toh mast hai bhai!",
        importance_score=7.0,
        category="electronics",
        brand="boAt",
        key_themes=["value", "quality"],
    )

    maybe_create_preference_or_belief(stream, evaluation)

    assert stream.size == 1
    node = stream.nodes[0]
    assert node.memory_type == MemoryType.PREFERENCE
    assert node.brand == "boAt"
    assert node.category == "electronics"


def test_low_score_creates_category_belief():
    """Evaluations with overall_score < 30 should create a CATEGORY_BELIEF memory node."""
    from synthetic_india.engine.simulation import maybe_create_preference_or_belief
    from synthetic_india.schemas.memory import MemoryType

    stream = MemoryStream(persona_id="test_persona")
    evaluation = PersonaEvaluation(
        evaluation_id="eval_low",
        run_id="run_test",
        creative_id="creative_test",
        persona_id="test_persona",
        primary_action="scroll_past",
        sentiment="very_negative",
        overall_score=15.0,
        attention_score=2.0,
        relevance_score=1.0,
        trust_score=2.0,
        desire_score=1.0,
        clarity_score=3.0,
        first_impression="Terrible",
        reasoning="Looks cheap and untrustworthy.",
        objections=["Fake claims", "No reviews"],
        verbatim_reaction="Yeh kya bakwas hai",
        importance_score=6.0,
        category="skincare",
        brand="ShadyBrand",
        key_themes=["distrust"],
    )

    maybe_create_preference_or_belief(stream, evaluation)

    assert stream.size == 1
    node = stream.nodes[0]
    assert node.memory_type == MemoryType.CATEGORY_BELIEF
    assert node.brand == "ShadyBrand"
    assert node.category == "skincare"


def test_mid_score_creates_no_extra_memory():
    """Evaluations with 30 <= overall_score <= 70 should NOT create preference or belief nodes."""
    from synthetic_india.engine.simulation import maybe_create_preference_or_belief

    stream = MemoryStream(persona_id="test_persona")
    evaluation = PersonaEvaluation(
        evaluation_id="eval_mid",
        run_id="run_test",
        creative_id="creative_test",
        persona_id="test_persona",
        primary_action="read",
        sentiment="neutral",
        overall_score=50.0,
        attention_score=5.0,
        relevance_score=5.0,
        trust_score=5.0,
        desire_score=5.0,
        clarity_score=5.0,
        first_impression="Meh",
        reasoning="Not bad, not great.",
        objections=[],
        verbatim_reaction="Theek hai",
        importance_score=4.0,
        category="fashion",
        brand="SomeStore",
        key_themes=["average"],
    )

    maybe_create_preference_or_belief(stream, evaluation)

    assert stream.size == 0
