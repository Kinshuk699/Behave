"""
Smoke test — run 1 creative (Zepto ad with image) against 5 personas.

Estimated cost: ~$0.09 (5 Haiku evals + 5 Sonnet critic + 1 Sonnet recommendation)
"""

import asyncio
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from synthetic_india.engine.simulation import load_personas, run_simulation
from synthetic_india.engine.cohort import select_cohort
from synthetic_india.schemas.creative import CreativeCard, CreativeFormat


async def main():
    # Build a Zepto creative with the actual ad image
    creative = CreativeCard(
        creative_id="zepto_ad_01",
        brand="Zepto",
        category="grocery_delivery",
        format=CreativeFormat.STATIC_IMAGE,
        headline="Zepto — Grocery Delivery in 10 Minutes",
        body_copy="Get groceries, snacks, and essentials delivered to your door in 10 minutes. Free delivery on first order.",
        cta_text="Order Now",
        cta_type="download_app",
        language_primary="English",
        code_mixed=False,
        image_path=os.path.join(os.path.dirname(__file__), "zepto.jpeg"),
    )

    print(f"Creative: {creative.brand} — {creative.headline}")
    print(f"Image: {creative.image_path}")
    print(f"Image exists: {os.path.isfile(creative.image_path)}")
    print()

    # Run with 5 personas (small cohort for smoke test)
    scorecards, recommendation, meta = await run_simulation(
        creatives=[creative],
        cohort_size=5,
        use_memory=True,
        use_embeddings=False,
    )

    print("\n" + "=" * 60)
    print(f"DONE — Run ID: {meta.run_id}")
    print(f"Cost: ${meta.total_cost_usd:.4f}")
    print(f"Tokens: {meta.total_tokens:,}")
    print(f"Evaluations: {meta.total_evaluations}")
    print(f"Quarantined: {meta.quarantined_records}")
    print(f"Results saved to: data/runs/{meta.run_id}/")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
