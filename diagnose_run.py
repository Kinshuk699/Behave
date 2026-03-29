"""Reproduce the Urban Company run failure with verbose error reporting."""
import asyncio
import base64
import tempfile
from pathlib import Path

from synthetic_india.config import get_llm_config
from synthetic_india.engine.simulation import load_personas, select_cohort
from synthetic_india.agents.persona_evaluator import evaluate_creative
from synthetic_india.schemas.creative import CreativeCard, CreativeFormat
from synthetic_india.memory.stream import MemoryStream
from synthetic_india.memory.consumer import MemoryScope


async def main():
    config = get_llm_config()
    print(f"Eval model: {config.eval_model}")

    # Mimic the exact dashboard flow
    brand = "Urban Company"
    category = "House Maintenance"

    creative = CreativeCard(
        creative_id="test_diag",
        brand=brand,
        category=category,
        format=CreativeFormat.STATIC_IMAGE,
        headline=f"{brand} ad",
        body_copy="",
        cta="Shop Now",
    )

    # Load personas and select cohort
    personas = load_personas()
    print(f"Loaded {len(personas)} personas")

    cohort = select_cohort(personas, category=category, cohort_size=5)
    print(f"Cohort: {len(cohort)} personas: {[p.name for p in cohort]}")

    # Try evaluating just the FIRST persona — catch the real error
    persona = cohort[0]
    stream = MemoryStream.load(persona.persona_id)

    print(f"\nEvaluating {persona.name}...")
    try:
        evaluation, response = await evaluate_creative(
            persona=persona,
            creative=creative,
            run_id="test_diag",
            memory_stream=stream,
            config=config,
            memory_scope=MemoryScope.CATEGORY,
        )
        print(f"SUCCESS: score={evaluation.overall_score}, verbatim={evaluation.verbatim_reaction[:80]}")
    except Exception as e:
        import traceback
        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
