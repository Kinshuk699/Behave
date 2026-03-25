# Medallion Pipeline — Bronze → Silver → Gold

**Status:** Built ✅
**Files:** `src/synthetic_india/pipeline/bronze.py`, `silver.py`, `gold.py`

## Why Medallion Architecture

This is the data engineering backbone. Every output from the simulation flows through three quality tiers—same pattern used at scale on Databricks/Delta Lake.

## The Three Layers

### Bronze (raw, append-only)
Everything as-is from the LLM. No filtering, no validation.
```
bronze/
├── creative_uploads/       raw ad data + CreativeCards
├── persona_evaluations/    raw LLM outputs per persona
├── memory_streams/         raw memory nodes per persona
└── run_metadata/           timestamps, costs, cohort info
```

### Silver (validated, quarantined)
Pydantic schema validation + **Critic Agent** quality gate.
```
silver/
├── validated_personas       Pydantic-checked profiles
├── validated_evaluations    schema-conforming + critic-passed evaluations
├── validated_memories       well-formed memory nodes
└── quarantine/              Critic FAIL + schema failures ← NEW in v2
```

### Gold (aggregated, analytics-ready)
Aggregated metrics consumed by the **Recommendation Agent** and end users.
```
gold/
├── creative_scorecards     per-creative aggregate metrics
├── segment_summaries       per-archetype roll-ups
├── memory_analytics        retrieval stats, reflection rates
├── critic_summaries        quality gate pass rates ← NEW in v2
└── run_summaries           cost, persona count, timing
```

## Capstone Framing

For the DataExpert capstone, this maps to:
- Bronze → Delta tables (append-only ingestion)
- Silver → DLT expectations (schema checks, quality rules)
- Gold → Unity Catalog analytics views
- Quarantine → DLT quarantine tables

## Data Flow

```
Persona Evaluation → raw eval
    │
    ▼
Bronze (append)
    │
    ▼
Silver (validate + quarantine via Critic Agent)
    │
    ▼
Gold (aggregate → CreativeScorecard, SegmentSummary)
    │
    ▼
Recommendation Agent → SCALE / ITERATE / KILL
```

## Next →

[Recommendation Agent](07-recommendation-agent.md) — decisions from gold-layer scorecards
