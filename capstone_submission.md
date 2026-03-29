# Capstone Submission — Behave (Synthetic India)

**Kinshuk Sahni · DataExpert Bootcamp · March 2026**

---


## My socials- https://www.linkedin.com/in/sahnikinshuk/ and https://kinshuksahni.com/

## Inspiration

Stanford research paper about generative agents-https://arxiv.org/abs/2304.03442

## Project Summary

**Behave** is an agentic creative testing platform that simulates how diverse Indian consumers would react to ad creatives — before a single rupee of ad spend is committed. A brand uploads an ad image and brand name; the system auto-extracts creative metadata via vision AI, selects a cohort of synthetic personas, runs vision-native evaluations, quality-gates each result through a Critic Agent, aggregates scores into a Medallion pipeline on Databricks, and outputs an actionable recommendation: **SCALE**, **ITERATE**, or **KILL** — with a prioritized edit playbook.

- **20 synthetic personas** across 8 behavioral archetypes, 10 Indian cities
- **18 canonical B2C categories** (from Quick Commerce to EdTech)
- **135 automated tests** (all green)
- **≈ ₹20 ($0.25) per simulation run**

---

## Course Technology Mapping

### Week 1 — AI Fundamentals: RAG, Chunking, Embeddings

| Course Concept                      | How Behave Uses It                                                                                                                                                                                                                                                                                                                                                 |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Chunking strategies**       | Persona "soul" profiles are structured into discrete chunks: demographics, purchase psychology, brand trust formation, category affinities, cultural context. This structured chunking allows the LLM to attend to specific behavioral dimensions during evaluation.                                                                                               |
| **RAG retrieval**             | Memory retrieval system (`src/synthetic_india/memory/retrieval.py`) scores memory nodes using `score = α·recency + β·relevance + γ·importance` — the same weighted retrieval pattern taught in Week 1. Currently using full-dump mode (200K context window makes retrieval optional for Phase 1), but the retrieval pipeline is implemented and tested. |
| **Embeddings for similarity** | Category affinity matching in cohort selection (`src/synthetic_india/engine/cohort.py`) ranks personas by affinity scores against extracted creative category — conceptually the same as embedding-based nearest-neighbor retrieval.                                                                                                                            |
| **Prompt engineering**        | Every agent (Creative Extractor, Persona Evaluator, Critic, Recommendation) uses carefully structured prompts with system/user separation, explicit output schemas, and few-shot behavioral grounding. Anti-sycophancy instructions in the Critic Agent prompt are a direct application of prompt engineering best practices.                                      |

### Week 2 — Delta Lake, Spark, Unity Catalog

| Course Concept                            | How Behave Uses It                                                                                                                                                                                 |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Delta Lake ACID transactions**    | All pipeline writes use Delta format for atomic, consistent writes. Evaluation results, memory nodes, and scorecard aggregates are written as Delta tables.                                        |
| **Unity Catalog 3-level namespace** | Tables organized as `catalog.schema.table` (e.g., `kinshuk_bronze.personas`, `kinshuk_silver.evaluations`, `kinshuk_gold.creative_scorecards`). Governed lineage from bronze through gold. |
| **Incremental processing**          | Bronze ingest (`src/synthetic_india/pipeline/databricks_bronze.py`) uses merge/upsert patterns — new simulation runs append, existing records are not duplicated.                               |
| **Schema enforcement**              | Silver layer validates every record against Pydantic schemas before write. Invalid records route to quarantine with rejection reasons — not silently dropped.                                     |
| **Time travel**                     | Delta's versioning enables cross-run comparison: "How did Persona X react to this brand's creative last week vs. today?" — stored as immutable snapshots.                                         |

### Week 3 — AI Functions, Synthetic Data, Structured Output

| Course Concept                                         | How Behave Uses It                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **AI_EXTRACT / AI_CLASSIFY / AI_PARSE_DOCUMENT** | The Creative Extractor (`src/synthetic_india/agents/creative_extractor.py`) is a direct analog of `AI_EXTRACT` + `AI_PARSE_DOCUMENT`: it takes a raw ad image and extracts structured fields (category, headline, CTA, brand positioning, visual style, price framing, festival context). Category assignment maps to `AI_CLASSIFY` against 18 canonical values. |
| **Structured output enforcement**                | Every LLM call returns Pydantic-validated output.`CreativeCard`, `EvaluationResult`, `CriticVerdict`, `Recommendation` — all defined in `src/synthetic_india/schemas/`. No free-text parsing; schema violations cause retry or quarantine.                                                                                                                    |
| **Synthetic data generation**                    | The entire persona library is synthetic data: 20 consumer profiles generated with deep behavioral realism — psychographics, purchase patterns, cultural context, language preferences, decision heuristics. Each persona is a structured JSON in `data/personas/`.                                                                                                    |
| **Parallel processing**                          | Persona evaluations run concurrently via `asyncio.gather()` in the simulation engine (`src/synthetic_india/engine/simulation.py`). Same pattern as Week 3's parallel AI function calls.                                                                                                                                                                              |

### Week 4 — Kafka, Streaming, DLT, Medallion Architecture

| Course Concept                                              | How Behave Uses It                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Medallion architecture (Bronze → Silver → Gold)** | Three explicit layers implemented in `src/synthetic_india/pipeline/`: `<br>`• **Bronze** (`bronze.py`, `databricks_bronze.py`): Raw ingestion of persona seeds, creative uploads, evaluations, critic verdicts, memory nodes, run metadata `<br>`• **Silver** (`silver.py`, `databricks_silver.py`): Schema validation, deduplication, score range checks, category vocabulary enforcement, quarantine routing `<br>`• **Gold** (`gold.py`, `databricks_gold.py`): Aggregated creative scorecards, segment summaries, run audit logs |
| **DLT-style expectations**                            | Silver layer implements expectation-style checks: required fields present, scores in 0–100 range, reasoning string ≥10 characters, category in allowed set, duplicate detection. Failed rows → quarantine table with specific rejection reasons. Mirrors DLT `EXPECT` / `EXPECT OR DROP` / `EXPECT OR FAIL` patterns.                                                                                                                                                                                                                                                |
| **Quarantine tables**                                 | Bad records are not dropped — they're routed to a quarantine table with structured rejection reasons. The Critic Agent adds a second quality gate: persona consistency, sycophancy detection, cultural authenticity, action-reasoning alignment. FAIL → quarantine.                                                                                                                                                                                                                                                                                                         |
| **Triggered micro-batch**                             | Not always-on streaming — deliberate design choice. Creative testing is request-driven. Each simulation triggers the full ingest → transform → aggregate pipeline. This mirrors the `availableNow=True` trigger pattern from Lab 1: process what's available, then stop.                                                                                                                                                                                                                                                                                                 |
| **Kappa-like architecture**                           | Single processing path from raw event to gold — no separate batch and streaming paths. Every simulation result flows through the same Bronze → Silver → Gold pipeline regardless of source (live dashboard simulation or batch replay).                                                                                                                                                                                                                                                                                                                                    |

### Week 5 — Agents, LangGraph, MLflow, Production Deployment

| Course Concept                                  | How Behave Uses It                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Agentic action (beyond summarization)** | Two agents that take real actions:`<br>`• **Critic Agent** (`src/synthetic_india/agents/critic_agent.py`): Quality gate that PASSes or FAILs evaluations — failed evals are quarantined, not just flagged. This is an agent that modifies the data pipeline. `<br>`• **Recommendation Agent** (`src/synthetic_india/agents/recommendation_agent.py`): Produces business decisions (SCALE/ITERATE/KILL) with specific edit playbook items. Not summarization — prescriptive action. |
| **Tool use / function calling**           | Creative Extractor uses vision + structured output as a "tool" — the simulation engine orchestrates: extract → evaluate → critique → recommend, with each step's output feeding the next. Same orchestration pattern as LangGraph nodes.                                                                                                                                                                                                                                                               |
| **MLflow experiment tracking**            | Every simulation run logged as an MLflow experiment (`src/synthetic_india/pipeline/mlflow_utils.py`): overall score, cost, token usage, critic pass rate, memory nodes created, model version. Enables cross-run comparison and regression detection.                                                                                                                                                                                                                                                    |
| **Guardrails / quality checks**           | Critic Agent implements guardrails: sycophancy detection (is the persona being unrealistically positive?), cultural authenticity (does a Lucknow persona actually sound like someone from Lucknow?), action-reasoning alignment (does the score match the stated action?).                                                                                                                                                                                                                                 |
| **Model serving**                         | Dashboard serves the full pipeline via FastAPI endpoints (`dashboard/app.py`). `/api/simulate` runs live inference; `/api/preloaded` serves cached case studies. Password-gated. Deployed to Render.                                                                                                                                                                                                                                                                                                 |
| **Asset Bundles**                         | `databricks.yml` at project root defines the Databricks Asset Bundle configuration for deploying notebooks and pipeline jobs to the workspace.                                                                                                                                                                                                                                                                                                                                                           |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    USER INTERFACE                          │
│  FastAPI Dashboard (brand name + ad image upload)         │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              CREATIVE EXTRACTOR (Vision AI)                │
│  Raw image → CreativeCard (category, headline, CTA,       │
│  brand positioning, visual style, price framing, etc.)    │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│               COHORT SELECTION ENGINE                      │
│  Category → persona affinities → rank + select top N      │
│  Optional: manual persona selection                       │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│          PERSONA EVALUATION (Vision-Native)                │
│  Each persona receives: soul profile + raw ad image +     │
│  CreativeCard + accumulated memories                      │
│  Output: 5 scores + action + verbatim + themes            │
│  Runs concurrently via asyncio.gather()                   │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              CRITIC AGENT (Quality Gate)                    │
│  Checks: persona consistency, sycophancy, cultural        │
│  authenticity, action-reasoning alignment                 │
│  PASS → pipeline  |  FAIL → quarantine                    │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│           MEDALLION PIPELINE (Databricks)                  │
│                                                           │
│  Bronze ─→ Silver ─→ Gold                                 │
│  (raw)    (validated)  (aggregated)                       │
│                                                           │
│  + Quarantine table   + MLflow logging                    │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│           RECOMMENDATION AGENT (Business Action)           │
│  Input: gold scorecard + segment summaries + verbatims    │
│  Output: SCALE / ITERATE / KILL + confidence +            │
│          prioritized edit playbook                        │
└──────────────────────────────────────────────────────────┘
```

---

## Data Sources (5 families)

| # | Source                        | Format                 | Description                                                |
| - | ----------------------------- | ---------------------- | ---------------------------------------------------------- |
| 1 | **Ad creative images**  | PNG/JPG (base64)       | Raw ad images uploaded by brand managers                   |
| 2 | **Persona library**     | JSON → Delta          | 20 structured persona profiles with deep behavioral fields |
| 3 | **Memory streams**      | JSON → Delta          | Append-only memory nodes from past ad exposures            |
| 4 | **Category benchmarks** | Python config → Delta | 18 B2C category definitions with affinity mappings         |
| 5 | **Run metadata**        | JSON → Delta          | Simulation run configs, timestamps, model versions, costs  |

---

## Data Quality Controls

| Layer  | Check                                | Action on Failure |
| ------ | ------------------------------------ | ----------------- |
| Silver | Required fields present              | → Quarantine     |
| Silver | Scores in 0–100 range               | → Quarantine     |
| Silver | Reasoning string ≥ 10 chars         | → Quarantine     |
| Silver | Category in canonical set of 18      | → Quarantine     |
| Silver | Duplicate detection                  | → Quarantine     |
| Silver | Persona schema validation (Pydantic) | → Quarantine     |
| Agent  | Persona consistency (Critic)         | → Quarantine     |
| Agent  | Sycophancy detection (Critic)        | → Quarantine     |
| Agent  | Cultural authenticity (Critic)       | → Quarantine     |
| Agent  | Action-reasoning alignment (Critic)  | → Quarantine     |

---

## Key Modules

| Module               | Path                                                   | Purpose                                                                         |
| -------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------- |
| Creative Extractor   | `src/synthetic_india/agents/creative_extractor.py`   | Vision AI image → structured CreativeCard                                      |
| Persona Evaluator    | `src/synthetic_india/agents/persona_evaluator.py`    | Vision-native persona reaction simulation                                       |
| Critic Agent         | `src/synthetic_india/agents/critic_agent.py`         | Quality gate — PASS/FAIL evaluations                                           |
| Recommendation Agent | `src/synthetic_india/agents/recommendation_agent.py` | Business decision + edit playbook                                               |
| Simulation Engine    | `src/synthetic_india/engine/simulation.py`           | Orchestrates full evaluation pipeline                                           |
| Cohort Selection     | `src/synthetic_india/engine/cohort.py`               | Category-based persona ranking                                                  |
| Memory Stream        | `src/synthetic_india/memory/stream.py`               | Append-only persona memory                                                      |
| Memory Consumer      | `src/synthetic_india/memory/consumer.py`             | Memory scoped retrieval for evaluation context                                  |
| Bronze Pipeline      | `src/synthetic_india/pipeline/bronze.py`             | Raw data ingestion                                                              |
| Silver Pipeline      | `src/synthetic_india/pipeline/silver.py`             | Validation + quarantine routing                                                 |
| Gold Pipeline        | `src/synthetic_india/pipeline/gold.py`               | Aggregation + scorecards                                                        |
| MLflow Utils         | `src/synthetic_india/pipeline/mlflow_utils.py`       | Experiment tracking per run                                                     |
| Databricks Ingest    | `src/synthetic_india/pipeline/databricks_ingest.py`  | Databricks-native pipeline execution                                            |
| Pydantic Schemas     | `src/synthetic_india/schemas/`                       | All data models (creative, evaluation, critic, recommendation, memory, persona) |
| Categories           | `src/synthetic_india/categories.py`                  | 18 canonical B2C category definitions                                           |
| Dashboard            | `dashboard/app.py`                                   | FastAPI endpoints for live simulation + preloaded case studies                  |
| Dashboard UI         | `dashboard/static/`                                  | Vanilla JS/HTML/CSS — Focus Group Chat, Score Breakdown, Creative Intelligence |

---

## Databricks Notebooks

| Notebook                              | Purpose                                                      |
| ------------------------------------- | ------------------------------------------------------------ |
| `notebooks/01_bronze_ingest.py`     | Ingest raw data into bronze Delta tables                     |
| `notebooks/02_silver_transform.py`  | Validate, clean, quarantine → silver tables                 |
| `notebooks/03_gold_materialize.py`  | Aggregate scores, build scorecards → gold tables            |
| `notebooks/04_simulation_ingest.py` | Triggered pipeline: ingest simulation run results end-to-end |

---

## If you guys have time please check out an app I built for journaling

https://apps.apple.com/us/app/bloom-your-pixel-journal/id6757811072
