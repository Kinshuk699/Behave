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
