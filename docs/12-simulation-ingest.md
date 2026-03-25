# Simulation Ingest — Real Data into Delta

**Status:** Built ✅ | Deployed ✅ | Run on Cluster ✅
**File:** `notebooks/04_simulation_ingest.py`

## What It Does

Takes raw simulation output from `data/runs/{RUN_ID}/` and pushes it through the full medallion pipeline into Databricks Delta tables. This is the bridge between "local Python simulation" and "enterprise data platform."

## Data Flow

```
data/runs/run_e3d656cc826e/
├── evaluations.json      ──► kinshuk_bronze.evaluations (append)
├── critic_verdicts.json  ──► kinshuk_bronze.critic_verdicts (append)
├── metadata.json         ──► kinshuk_bronze.run_metadata (append)
├── scorecards.json       ──► kinshuk_gold.creative_scorecards (append)
└── recommendation.json        (logged as MLflow artifact)

Bronze → Silver: validation (reasoning >= 10 chars, verbatim >= 5 chars)
Silver → Gold: aggregation (per-creative scorecards + audit log)
```

## Key Decisions

- **Append mode** — Safe to re-run for different RUN_IDs. Dedup via Delta time travel if needed.
- **Explicit schemas** — Spark can't infer types from None values. We serialize Nones to `""`.
- **Match existing table schemas** — ACLs prevent auto-migration, so we drop extra columns.

## Bugs Fixed During Deployment

1. `CANNOT_DETERMINE_TYPE` — Spark schema inference fails on None → convert to `""`
2. `_LEGACY_ERROR_TEMP_DELTA_0007` — Schema mismatch on audit log → removed extra columns

## Next →

[MLflow Tracking](13-mlflow-tracking.md) — experiment logging for run comparison
