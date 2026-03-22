"""Quick validation that all modules import and work correctly."""

from synthetic_india.schemas.persona import PersonaProfile
from synthetic_india.schemas.creative import CreativeCard
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.memory import MemoryNode, MemoryStreamState
from synthetic_india.schemas.recommendation import AgentRecommendation
from synthetic_india.memory.stream import MemoryStream
from synthetic_india.memory.retrieval import MemoryRetriever, ReflectionEngine
from synthetic_india.engine.cohort import select_cohort
from synthetic_india.engine.simulation import load_personas
from synthetic_india.cli import build_demo_creatives
from synthetic_india.pipeline.silver import validate_persona, validate_creative_card

# Load personas
personas = load_personas()
print(f"Loaded {len(personas)} personas:")
for p in personas:
    print(f"  {p.name} ({p.archetype}) -- {p.tagline}")

# Load demo creatives
creatives = build_demo_creatives()
print(f"\nDemo creatives: {len(creatives)}")
for c in creatives:
    print(f"  {c.creative_id}: {c.brand} -- {c.headline[:60]}")

# Test cohort selection
cohort = select_cohort(personas, "skincare")
print(f"\nSkincare cohort ({len(cohort)} personas):")
for p in cohort:
    print(f"  {p.name}")

# Test memory stream
stream = MemoryStream("researcher_delhi_01")
print(f"\nMemory stream for researcher: {stream.size} nodes")

# Test retriever
retriever = MemoryRetriever()
print(f"Retriever weights: recency={retriever.config.recency_weight}, relevance={retriever.config.relevance_weight}, importance={retriever.config.importance_weight}")

# Test silver validation
print("\nSilver validation:")
for p_data in [p.model_dump() for p in personas]:
    persona, result = validate_persona(p_data)
    status = "PASS" if result.passed else f"FAIL: {result.errors}"
    print(f"  Validate {p_data['persona_id']}: {status}")

print("\nAll imports and validations passed!")
