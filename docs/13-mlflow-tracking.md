# MLflow Tracking — Experiment Logging

**Status:** Built ✅ | Deployed ✅ | Verified on Cluster ✅
**Files:** `src/synthetic_india/pipeline/mlflow_utils.py`, Section 5 of `notebooks/04_simulation_ingest.py`

## What It Does

Logs every simulation run as an MLflow experiment so you can **compare runs side-by-side** without writing SQL. Each run records what was tested (params), how it performed (metrics), and the raw evidence (artifacts).

## Why It Matters

| Without MLflow | With MLflow |
|---|---|
| Write SQL to compare runs | Click "Compare" in UI |
| No cost history | Cost tracked per run |
| Manual artifact management | Artifacts versioned automatically |
| No experiment lineage | Full history of every test |

## What Gets Logged

**Params** (what was tested):
- `run_id`, `brand`, `category`, `cohort_size`

**Metrics** (how it performed):
- `avg_overall_score` — headline quality metric
- `total_cost_usd` — API cost for the run
- `total_tokens` — total LLM tokens consumed
- `n_personas_evaluated` — cohort size that completed
- `quarantine_rate` — fraction flagged by Critic Agent

**Artifacts** (the receipts):
- `evaluations.json` — raw persona evaluations
- `recommendation.json` — final SCALE/ITERATE/KILL decision

## Experiment Location

```
Experiment: /Users/kinshuk.sahni6@gmail.com/synthetic_india
ID: 898817165102177
```

## Helper Module

`build_mlflow_payload(metadata, scorecard)` in `mlflow_utils.py` — pure function that builds the params/metrics dict. Tested locally (no MLflow dependency needed).

## Next →

[Dashboard](14-dashboard.md) — Live demo site on Render with pre-loaded Zepto data + live simulation
