"""
CLI entry point — run a simulation from the command line.

Usage:
  python -m synthetic_india.cli run --brand "Minimalist" --category "skincare" --text "Your ad copy here"
  python -m synthetic_india.cli demo   # Run with sample creatives
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console

from synthetic_india.engine.simulation import load_personas, run_simulation
from synthetic_india.schemas.creative import CreativeCard, CreativeFormat
from synthetic_india.schemas.recommendation import RunMetadata
from synthetic_india.schemas.critic import CriticRunSummary

console = Console()


def print_run_header(
    creatives: list[CreativeCard],
    console: Console = console,
) -> None:
    """Print what's about to be evaluated before a simulation starts."""
    console.print("\n[bold cyan]Synthetic India — Creative Evaluation[/bold cyan]")
    console.print(f"Creatives to evaluate: {len(creatives)}")
    for c in creatives:
        console.print(f"  • [bold]{c.brand}[/bold] ({c.category}): {c.headline}")
    console.print()


def print_run_summary(
    meta: RunMetadata,
    critic_summary: CriticRunSummary | None = None,
    console: Console = console,
) -> None:
    """Print post-run summary with key metrics."""
    console.print(f"\n[bold green]Run complete![/bold green]")
    console.print(f"  Run ID:      {meta.run_id}")
    console.print(f"  Evaluations: {meta.total_evaluations}")
    console.print(f"  Cost:        ${meta.total_cost_usd:.4f}")
    console.print(f"  Tokens:      {meta.total_tokens:,}")
    console.print(f"  Status:      {meta.status}")
    if meta.quarantined_records:
        console.print(f"  Quarantined: {meta.quarantined_records}")
    if critic_summary:
        console.print(f"\n  [bold]Critic Quality Gate[/bold]")
        console.print(f"    Pass rate:    {critic_summary.pass_rate:.0%}")
        console.print(f"    Passed:       {critic_summary.total_passed}")
        console.print(f"    Failed:       {critic_summary.total_failed}")
        console.print(f"    Quality:      {critic_summary.overall_quality_score:.1f}/10")


def build_demo_creatives() -> list[CreativeCard]:
    """Build sample creatives for demo/testing."""
    return [
        CreativeCard(
            creative_id="demo_creative_01",
            brand="Minimalist",
            category="skincare",
            format=CreativeFormat.STATIC_IMAGE,
            headline="10% Niacinamide Serum — Dermatologist Tested",
            body_copy="Targets acne marks, uneven skin tone & enlarged pores. 100% transparent ingredient list. No fragrance. No hidden chemicals.",
            cta_text="Shop Now at ₹599",
            cta_type="buy",
            price_shown=599,
            original_price=699,
            discount_percentage=14,
            price_framing="value",
            urgency_cues=[],
            social_proof_cues=["50,000+ reviews", "4.3★ rating", "#1 Niacinamide in India"],
            trust_signals=["Dermatologist tested", "Made Safe certified", "Full ingredient list shown"],
            emotional_hooks=["Transparency", "Science-backed skincare"],
            visual_style="minimal",
            color_dominant="white",
            product_visibility=0.9,
            human_presence=False,
            celebrity_present=False,
            language_primary="English",
            code_mixed=False,
        ),
        CreativeCard(
            creative_id="demo_creative_02",
            brand="Dot & Key",
            category="skincare",
            format=CreativeFormat.STATIC_IMAGE,
            headline="VITAMIN C + E Glow Serum ✨ Get That Lit-From-Within Look!",
            body_copy="Your skin deserves the glow-up! Join 2 lakh+ happy customers. Limited edition summer packaging!",
            cta_text="Grab Yours — Only ₹695!",
            cta_type="buy",
            price_shown=695,
            original_price=895,
            discount_percentage=22,
            price_framing="discount",
            urgency_cues=["Limited edition packaging!", "Selling fast 🔥"],
            social_proof_cues=["2 lakh+ happy customers", "Trending on Instagram"],
            trust_signals=[],
            emotional_hooks=["Glow-up narrative", "FOMO", "Aspirational lifestyle", "Treat yourself"],
            visual_style="bold_graphic",
            color_dominant="orange-yellow",
            product_visibility=0.8,
            human_presence=True,
            celebrity_present=False,
            language_primary="English",
            code_mixed=True,
        ),
        CreativeCard(
            creative_id="demo_creative_03",
            brand="Mamaearth",
            category="skincare",
            format=CreativeFormat.STATIC_IMAGE,
            headline="Diwali Glow Sale ✨ Ubtan Face Wash — Haldi & Saffron!",
            body_copy="Is Diwali pe apni skin ko de natural glow! Ubtan Face Wash with haldi, saffron & rose water. Paraben-free. Join 50 lakh+ happy customers.",
            cta_text="Shop Now — ₹349 Only!",
            cta_type="buy",
            price_shown=349,
            original_price=499,
            discount_percentage=30,
            price_framing="discount",
            urgency_cues=["Diwali Sale — ends soon!", "Limited stock 🔥"],
            social_proof_cues=["50 lakh+ happy customers", "India's #1 toxin-free brand"],
            trust_signals=["Made Safe certified", "Paraben-free", "Dermatologist approved"],
            emotional_hooks=["Festival glow", "Natural beauty", "Family gifting"],
            visual_style="traditional",
            color_dominant="gold-orange",
            product_visibility=0.85,
            human_presence=True,
            celebrity_present=False,
            language_primary="Hindi",
            language_secondary="English",
            code_mixed=True,
            festival_context="Diwali",
            target_city_tier="Pan-India",
            cultural_references=["haldi ceremony", "diyas", "family gathering", "rangoli"],
        ),
    ]


async def cmd_run(args: argparse.Namespace) -> None:
    """Run a simulation with provided creative details."""
    creative = CreativeCard(
        creative_id=f"cli_{args.brand.lower().replace(' ', '_')}",
        brand=args.brand,
        category=args.category,
        format=CreativeFormat.STATIC_IMAGE,
        headline=args.text,
        body_copy=args.body or None,
        cta_text=args.cta or None,
        language_primary="English",
    )

    print_run_header(creatives=[creative])

    scorecards, recommendation, meta = await run_simulation(
        creatives=[creative],
        use_memory=not args.no_memory,
    )
    print_run_summary(meta=meta)


async def cmd_demo(args: argparse.Namespace) -> None:
    """Run a demo simulation with sample creatives."""
    console.print("[bold]Running Synthetic India demo simulation[/bold]\n")

    creatives = build_demo_creatives()
    console.print(f"Demo creatives: {len(creatives)}")
    for c in creatives:
        console.print(f"  - {c.creative_id}: {c.brand} — {c.headline}")

    personas = load_personas()
    console.print(f"Personas loaded: {len(personas)}")
    for p in personas:
        console.print(f"  - {p.name} ({p.archetype}): {p.tagline}")

    console.print()
    print_run_header(creatives=creatives)

    scorecards, recommendation, meta = await run_simulation(
        creatives=creatives,
        personas=personas,
        use_memory=not args.no_memory,
    )
    print_run_summary(meta=meta)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synthetic India: Agentic Creative Testing Platform"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a simulation")
    run_parser.add_argument("--brand", required=True, help="Brand name")
    run_parser.add_argument("--category", required=True, help="Product category")
    run_parser.add_argument("--text", required=True, help="Headline / ad copy")
    run_parser.add_argument("--body", help="Body copy")
    run_parser.add_argument("--cta", help="CTA text")
    run_parser.add_argument("--no-memory", action="store_true", help="Disable memory retrieval")

    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run demo simulation")
    demo_parser.add_argument("--no-memory", action="store_true", help="Disable memory retrieval")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "demo":
        asyncio.run(cmd_demo(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
