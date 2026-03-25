"""
Simulation Engine — orchestrates a complete simulation run.

This is the main entry point for running creative evaluations.
It coordinates:
  1. Loading personas and creatives
  2. Selecting cohorts
  3. Loading/creating memory streams
  4. Running persona evaluations (with long-horizon memory retrieval)
  5. Triggering reflections when importance threshold is crossed
  6. Aggregating results into scorecards
  7. Generating agentic recommendations
  8. Persisting all data (pipeline-ready)

Designed to run locally first, then map directly to Databricks notebooks.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from synthetic_india.agents import critic_agent
from synthetic_india.agents.llm_client import call_anthropic
from synthetic_india.agents.persona_evaluator import evaluate_creative
from synthetic_india.agents.recommendation_agent import generate_recommendation
from synthetic_india.config import (
    DATA_DIR,
    PERSONAS_DIR,
    RUNS_DIR,
    get_llm_config,
    get_memory_config,
    get_pipeline_config,
)
from synthetic_india.engine.cohort import select_cohort
from synthetic_india.memory.retrieval import ReflectionEngine
from synthetic_india.memory.stream import MemoryStream
from synthetic_india.schemas.creative import CreativeCard
from synthetic_india.schemas.critic import CriticRunSummary, CriticVerdict
from synthetic_india.schemas.evaluation import (
    CreativeScorecard,
    PersonaEvaluation,
    SegmentSummary,
)
from synthetic_india.schemas.persona import PersonaProfile
from synthetic_india.schemas.recommendation import AgentRecommendation, RunMetadata

console = Console()


def load_personas(directory: Optional[Path] = None) -> list[PersonaProfile]:
    """Load all persona profiles from JSON files."""
    persona_dir = directory or PERSONAS_DIR
    personas = []
    for path in sorted(persona_dir.glob("*.json")):
        data = json.loads(path.read_text())
        personas.append(PersonaProfile.model_validate(data))
    return personas


def _grade_score(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


def aggregate_evaluations(
    evaluations: list[PersonaEvaluation],
    personas: list[PersonaProfile],
    creative: CreativeCard,
    run_id: str,
) -> CreativeScorecard:
    """
    Aggregate individual evaluations into a creative scorecard.

    This produces the gold-layer aggregation that the recommendation
    agent consumes.
    """
    if not evaluations:
        return CreativeScorecard(
            run_id=run_id,
            creative_id=creative.creative_id,
            brand=creative.brand,
            category=creative.category,
            n_personas_evaluated=0,
            overall_score=0,
            grade="F",
            action_distribution={},
            sentiment_distribution={},
            avg_attention=0,
            avg_relevance=0,
            avg_trust=0,
            avg_desire=0,
            avg_clarity=0,
            top_strengths=[],
            top_weaknesses=[],
            top_verbatims=[],
        )

    persona_map = {p.persona_id: p for p in personas}
    n = len(evaluations)

    action_dist = dict(Counter(e.primary_action for e in evaluations))
    sentiment_dist = dict(Counter(e.sentiment for e in evaluations))

    avg_score = sum(e.overall_score for e in evaluations) / n
    avg_attention = sum(e.attention_score for e in evaluations) / n
    avg_relevance = sum(e.relevance_score for e in evaluations) / n
    avg_trust = sum(e.trust_score for e in evaluations) / n
    avg_desire = sum(e.desire_score for e in evaluations) / n
    avg_clarity = sum(e.clarity_score for e in evaluations) / n

    # Top verbatims: pick diverse, interesting ones
    sorted_evals = sorted(evaluations, key=lambda e: e.overall_score, reverse=True)
    top_verbatims = [e.verbatim_reaction for e in sorted_evals[:5]]

    # Theme analysis
    all_themes = []
    for e in evaluations:
        all_themes.extend(e.key_themes)
    theme_counts = Counter(all_themes)

    # Strengths = high-scoring dimensions, weaknesses = low-scoring
    dim_scores = {
        "attention": avg_attention,
        "relevance": avg_relevance,
        "trust": avg_trust,
        "desire": avg_desire,
        "clarity": avg_clarity,
    }
    strengths = [k for k, v in sorted(dim_scores.items(), key=lambda x: x[1], reverse=True) if v >= 6.0]
    weaknesses = [k for k, v in sorted(dim_scores.items(), key=lambda x: x[1]) if v < 5.0]

    # Add theme-based strengths/weaknesses
    positive_themes = [t for t, c in theme_counts.most_common(3)]
    strengths.extend([f"strong {t}" for t in positive_themes[:2]])

    # Common objections
    all_objections = []
    for e in evaluations:
        all_objections.extend(e.objections)
    top_objections = [obj for obj, _ in Counter(all_objections).most_common(3)]
    weaknesses.extend(top_objections[:2])

    # Segment summaries by archetype
    segment_summaries = []
    by_archetype: dict[str, list[PersonaEvaluation]] = defaultdict(list)
    for e in evaluations:
        persona = persona_map.get(e.persona_id)
        if persona:
            by_archetype[persona.archetype].append(e)

    for archetype, arch_evals in by_archetype.items():
        an = len(arch_evals)
        seg_action_dist = dict(Counter(e.primary_action for e in arch_evals))
        seg_sent_dist = dict(Counter(e.sentiment for e in arch_evals))
        seg_objections = []
        seg_themes = []
        for e in arch_evals:
            seg_objections.extend(e.objections)
            seg_themes.extend(e.key_themes)

        segment_summaries.append(
            SegmentSummary(
                run_id=run_id,
                creative_id=creative.creative_id,
                segment_name=archetype,
                segment_type="archetype",
                n_personas=an,
                avg_score=sum(e.overall_score for e in arch_evals) / an,
                action_distribution=seg_action_dist,
                sentiment_distribution=seg_sent_dist,
                avg_attention=sum(e.attention_score for e in arch_evals) / an,
                avg_relevance=sum(e.relevance_score for e in arch_evals) / an,
                avg_trust=sum(e.trust_score for e in arch_evals) / an,
                avg_desire=sum(e.desire_score for e in arch_evals) / an,
                avg_clarity=sum(e.clarity_score for e in arch_evals) / an,
                top_objections=[o for o, _ in Counter(seg_objections).most_common(2)],
                top_themes=[t for t, _ in Counter(seg_themes).most_common(3)],
                representative_verbatim=arch_evals[0].verbatim_reaction,
            )
        )

    return CreativeScorecard(
        run_id=run_id,
        creative_id=creative.creative_id,
        brand=creative.brand,
        category=creative.category,
        n_personas_evaluated=n,
        overall_score=avg_score,
        grade=_grade_score(avg_score),
        action_distribution=action_dist,
        sentiment_distribution=sentiment_dist,
        avg_attention=avg_attention,
        avg_relevance=avg_relevance,
        avg_trust=avg_trust,
        avg_desire=avg_desire,
        avg_clarity=avg_clarity,
        top_strengths=strengths[:5],
        top_weaknesses=weaknesses[:5],
        top_verbatims=top_verbatims,
        segment_summaries=segment_summaries,
    )


async def run_simulation(
    creatives: list[CreativeCard],
    personas: Optional[list[PersonaProfile]] = None,
    cohort_size: int = 20,
    use_memory: bool = True,
    use_embeddings: bool = False,
    run_id: Optional[str] = None,
) -> tuple[list[CreativeScorecard], Optional[AgentRecommendation], RunMetadata]:
    """
    Execute a complete simulation run.

    End-to-end flow:
    1. Load personas (or use provided ones)
    2. For each creative: select cohort -> evaluate -> aggregate
    3. Generate recommendation across all creatives
    4. Persist results and memories

    Args:
        creatives: Creative cards to evaluate
        personas: Persona library (loaded from disk if not provided)
        cohort_size: Number of personas per creative
        use_memory: Whether to use long-horizon memory retrieval
        use_embeddings: Whether to use dense embeddings for retrieval
        run_id: Optional run identifier

    Returns:
        Tuple of (scorecards, recommendation, run_metadata)
    """
    run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    config = get_llm_config()
    mem_config = get_memory_config()

    # Load personas
    if personas is None:
        personas = load_personas()
        console.print(f"[bold]Loaded {len(personas)} personas[/bold]")

    # Track run metadata
    all_persona_ids = set()
    all_evaluations: list[PersonaEvaluation] = []
    all_scorecards: list[CreativeScorecard] = []
    all_verdicts: list[CriticVerdict] = []
    quarantined_evaluations: list[PersonaEvaluation] = []
    total_cost = 0.0
    total_tokens = 0

    started_at = datetime.utcnow()

    for creative in creatives:
        console.print(f"\n[bold cyan]Evaluating creative: {creative.creative_id}[/bold cyan]")
        console.print(f"  Brand: {creative.brand} | Category: {creative.category}")

        # Select cohort
        cohort = select_cohort(
            personas,
            category=creative.category,
            cohort_size=cohort_size,
        )
        console.print(f"  Cohort: {len(cohort)} personas selected")

        # Load or create memory streams
        memory_streams: dict[str, MemoryStream] = {}
        if use_memory:
            for p in cohort:
                memory_streams[p.persona_id] = MemoryStream.load(p.persona_id)

        # Evaluate each persona
        evaluations: list[PersonaEvaluation] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Running {len(cohort)} evaluations...", total=len(cohort)
            )

            for persona in cohort:
                stream = memory_streams.get(persona.persona_id) if use_memory else None

                try:
                    evaluation, response = await evaluate_creative(
                        persona=persona,
                        creative=creative,
                        run_id=run_id,
                        memory_stream=stream,
                        config=config,
                        use_embeddings=use_embeddings,
                    )

                    all_persona_ids.add(persona.persona_id)
                    total_cost += evaluation.cost_usd
                    total_tokens += evaluation.prompt_tokens + evaluation.completion_tokens

                    # Critic quality gate
                    try:
                        verdict = await critic_agent.evaluate_single(
                            persona=persona,
                            evaluation=evaluation,
                            config=config,
                        )
                        all_verdicts.append(verdict)
                        total_cost += verdict.cost_usd

                        if verdict.passed:
                            evaluations.append(evaluation)
                        else:
                            quarantined_evaluations.append(evaluation)
                            console.print(
                                f"  [yellow]Quarantined {persona.name}: "
                                f"{verdict.explanation}[/yellow]"
                            )
                    except Exception as critic_err:
                        console.print(
                            f"  [yellow]Critic failed for {persona.name}: {critic_err} "
                            f"— evaluation included anyway[/yellow]"
                        )
                        evaluations.append(evaluation)

                    progress.update(task, advance=1)

                except Exception as e:
                    console.print(f"  [red]Failed for {persona.name}: {e}[/red]")
                    progress.update(task, advance=1)

        # Check for reflections
        if use_memory:
            reflection_engine = ReflectionEngine()
            for persona in cohort:
                stream = memory_streams.get(persona.persona_id)
                if stream and stream.should_reflect:
                    console.print(
                        f"  [yellow]Triggering reflection for {persona.name} "
                        f"(importance: {stream._importance_since_reflection:.1f})[/yellow]"
                    )
                    focal_nodes = reflection_engine.select_focal_nodes(stream.nodes)
                    prompt = reflection_engine.generate_reflection_prompt(
                        focal_nodes, persona.name
                    )

                    try:
                        resp = await call_anthropic(
                            prompt=prompt, model=config.reflection_model, config=config
                        )
                        insights = [
                            line.strip()
                            for line in resp.content.strip().split("\n")
                            if line.strip()
                        ]
                        for insight in insights:
                            stream.add_reflection(
                                description=insight,
                                importance=7.0,
                                evidence_node_ids=[n.node_id for n in focal_nodes[:5]],
                                category=creative.category,
                            )
                        total_cost += resp.cost_usd
                        total_tokens += resp.prompt_tokens + resp.completion_tokens
                    except Exception as e:
                        console.print(f"  [red]Reflection failed: {e}[/red]")

            # Persist memory streams
            for stream in memory_streams.values():
                stream.save()

        # Critic summary for this creative
        creative_verdicts = [
            v for v in all_verdicts
            if v.evaluation_id in {e.evaluation_id for e in evaluations + quarantined_evaluations}
        ]
        if creative_verdicts:
            critic_summary = critic_agent.summarize_run(run_id, creative_verdicts)
            _print_critic_summary(critic_summary)

        # Aggregate (only passed evaluations)
        scorecard = aggregate_evaluations(evaluations, personas, creative, run_id)
        all_scorecards.append(scorecard)
        all_evaluations.extend(evaluations)

        # Print summary
        _print_scorecard(scorecard)

    # Generate recommendation
    recommendation = None
    if all_scorecards:
        console.print("\n[bold magenta]Generating recommendation...[/bold magenta]")
        try:
            recommendation, resp = await generate_recommendation(
                all_scorecards, run_id, config
            )
            total_cost += recommendation.cost_usd
            total_tokens += recommendation.prompt_tokens + recommendation.completion_tokens
            _print_recommendation(recommendation)
        except Exception as e:
            console.print(f"[red]Recommendation failed: {e}[/red]")

    completed_at = datetime.utcnow()

    # Build run metadata
    run_meta = RunMetadata(
        run_id=run_id,
        brand=creatives[0].brand if creatives else "",
        category=creatives[0].category if creatives else "",
        creative_ids=[c.creative_id for c in creatives],
        persona_ids=list(all_persona_ids),
        cohort_size=len(all_persona_ids),
        total_evaluations=len(all_evaluations),
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        successful_evaluations=len(all_evaluations),
        quarantined_records=len(quarantined_evaluations),
        failed_evaluations=0,
    )

    # Persist run results
    _save_run(run_meta, all_evaluations, all_scorecards, recommendation, all_verdicts)

    console.print(f"\n[bold green]Run complete![/bold green]")
    console.print(f"  Run ID: {run_id}")
    console.print(f"  Evaluations: {len(all_evaluations)}")
    console.print(f"  Total cost: ${total_cost:.4f}")
    console.print(f"  Total tokens: {total_tokens:,}")

    return all_scorecards, recommendation, run_meta


def _save_run(
    run_meta: RunMetadata,
    evaluations: list[PersonaEvaluation],
    scorecards: list[CreativeScorecard],
    recommendation: Optional[AgentRecommendation],
    verdicts: Optional[list[CriticVerdict]] = None,
) -> Path:
    """Persist all run outputs to JSON files."""
    run_dir = RUNS_DIR / run_meta.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "metadata.json").write_text(run_meta.model_dump_json(indent=2))
    (run_dir / "evaluations.json").write_text(
        json.dumps([e.model_dump(mode="json") for e in evaluations], indent=2, default=str)
    )
    (run_dir / "scorecards.json").write_text(
        json.dumps([s.model_dump(mode="json") for s in scorecards], indent=2, default=str)
    )
    if recommendation:
        (run_dir / "recommendation.json").write_text(
            recommendation.model_dump_json(indent=2)
        )
    if verdicts:
        critic_summary = critic_agent.summarize_run(run_meta.run_id, verdicts)
        (run_dir / "critic_verdicts.json").write_text(
            json.dumps([v.model_dump(mode="json") for v in verdicts], indent=2, default=str)
        )
        (run_dir / "critic_summary.json").write_text(
            critic_summary.model_dump_json(indent=2)
        )

    return run_dir


def _print_critic_summary(summary: CriticRunSummary) -> None:
    """Pretty-print critic quality gate results."""
    table = Table(title="Critic Quality Gate")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Evaluated", str(summary.total_evaluated))
    table.add_row("Passed", f"[green]{summary.total_passed}[/green]")
    table.add_row("Failed (Quarantined)", f"[red]{summary.total_failed}[/red]")
    table.add_row("Pass Rate", f"{summary.pass_rate:.0%}")
    table.add_row("Avg Persona Consistency", f"{summary.avg_persona_consistency:.1f}/10")
    table.add_row("Avg Sycophancy", f"{summary.avg_sycophancy_score:.1f}/10")
    table.add_row("Avg Cultural Authenticity", f"{summary.avg_cultural_authenticity:.1f}/10")
    table.add_row("Avg Action-Reasoning Align", f"{summary.avg_action_reasoning_alignment:.1f}/10")
    table.add_row("Overall Quality", f"{summary.overall_quality_score:.1f}/10")

    console.print(table)

    # Show individual contributions
    if summary.quality_contributions:
        contrib_table = Table(title="Per-Persona Contribution")
        contrib_table.add_column("Persona", style="cyan")
        contrib_table.add_column("Quality", style="white")
        contrib_table.add_column("Weight", style="white")
        contrib_table.add_column("Status", style="white")

        for c in summary.quality_contributions:
            status = "[green]PASS[/green]" if c["passed"] else "[red]FAIL[/red]"
            contrib_table.add_row(
                c["persona_id"],
                f"{c['overall_quality']:.1f}",
                f"{c['weight']:.1%}",
                status,
            )

        console.print(contrib_table)


def _print_scorecard(scorecard: CreativeScorecard) -> None:
    """Pretty-print a scorecard."""
    table = Table(title=f"Scorecard: {scorecard.creative_id} ({scorecard.grade})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Overall Score", f"{scorecard.overall_score:.1f}/100")
    table.add_row("Personas", str(scorecard.n_personas_evaluated))
    table.add_row("Attention", f"{scorecard.avg_attention:.1f}/10")
    table.add_row("Relevance", f"{scorecard.avg_relevance:.1f}/10")
    table.add_row("Trust", f"{scorecard.avg_trust:.1f}/10")
    table.add_row("Desire", f"{scorecard.avg_desire:.1f}/10")
    table.add_row("Clarity", f"{scorecard.avg_clarity:.1f}/10")
    table.add_row("Actions", str(scorecard.action_distribution))
    table.add_row("Sentiment", str(scorecard.sentiment_distribution))

    console.print(table)


def _print_recommendation(rec: AgentRecommendation) -> None:
    """Pretty-print a recommendation."""
    console.print(f"\n[bold]Recommendation: {rec.recommended_action.upper()}[/bold]")
    console.print(f"  Confidence: {rec.confidence_score:.0%}")
    console.print(f"  {rec.reasoning_summary}")
    if rec.winning_creative_id:
        console.print(f"  Winner: {rec.winning_creative_id}")
    if rec.top_risks:
        console.print(f"  Risks: {', '.join(rec.top_risks)}")
    if rec.edit_recommendations:
        console.print("  Edit suggestions:")
        for er in rec.edit_recommendations:
            console.print(f"    [{er.priority}] {er.element}: {er.suggested_change}")
