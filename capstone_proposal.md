# Capstone Project Proposal

**Student:** Kinshuk Sahni
**Project Title:** Behave — An Agentic Creative Testing Platform for Indian D2C Brands
**Date:** March 2026

---

## 1. Problem Statement

Indian D2C brands spend crores on digital advertising, yet most creative decisions are made by intuition — run the ad, burn the budget, learn after the fact. A/B testing helps, but it's slow, expensive, and only tests live audiences. There's no way to pre-test how different consumer segments will react before committing ad spend.

**Behave** solves this by simulating realistic Indian consumer reactions to ad creatives using AI-powered synthetic personas — all processed through a Databricks-native data pipeline with full medallion architecture, quality controls, and agentic decision-making.

---

## 2. How This Connects to the Course

This project directly applies techniques from every major module of the DataExpert bootcamp:

| Course Module                                             | How I Plan to Use It                                                                                                                                                                                                                                                                                                                                                                                 |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Lakehouse Architecture (Week 1)**                 | The entire backend runs on Delta Lake tables inside Databricks. I chose Delta over raw Parquet for ACID compliance (evaluation writes must be atomic) and time-travel (comparing creative performance across runs).                                                                                                                                                                                  |
| **Data Governance & Unity Catalog (Week 1, Day 2)** | All tables live under a governed catalog (`bootcamp_students`) with schema-level isolation (`kinshuk_bronze`, `kinshuk_silver`, `kinshuk_gold`). Lineage tracking shows how raw evaluations flow through to final scorecards.                                                                                                                                                                |
| **Spark & Distributed Compute (Week 2)**            | The medallion pipeline notebooks use Spark DataFrames for transformations — exploding nested JSON evaluations, joining persona metadata, computing segment-level aggregates. While my data volume doesn't require petabyte-scale optimization, I apply join strategies and schema enforcement patterns from the Spark deep-dive.                                                                    |
| **Chunking & RAG Patterns (Week 3)**                | The persona memory system is conceptually a RAG pattern — each persona accumulates observation nodes from prior ad exposures, and the system retrieves relevant memories (by category, brand, or full scope) to contextualize new evaluations. This is retrieval-augmented generation applied to consumer memory, not document Q&A.                                                                 |
| **Streaming & Delta Live Tables (Week 4)**          | I plan to use triggered batch execution rather than always-on streaming — this is a deliberate design choice. Creative testing is request-driven (a brand submits an ad, the pipeline runs, results return). This aligns with the course guidance that streaming should match the business cadence. I use DLT-style expectations for data quality checks and quarantine routing in my silver layer. |
| **Agentic Systems (Week 5)**                        | Two distinct agents with different roles: a**Critic Agent** that acts as a quality gate (evaluating persona consistency, sycophancy, cultural authenticity) and a **Recommendation Agent** that takes concrete business actions (SCALE / ITERATE / KILL / SPLIT decisions with prioritized edit suggestions).                                                                            |

---

## 3. Architecture & Data Flow

### 3.1 The End-to-End Flow

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  Dashboard   │────▶│  Databricks  │────▶│   LLM Agents  │────▶│  Databricks  │
│  (Website)   │     │  (READ)      │     │  (Evaluate +  │     │  (WRITE)     │
│              │◀────│  Personas +  │     │   Critic +    │◀────│  Bronze →    │
│  Results     │     │  Memories    │     │   Recommend)  │     │  Silver →    │
│  Displayed   │     │              │     │               │     │  Gold +      │
│              │     │              │     │               │     │  MLflow      │
└─────────────┘     └──────────────┘     └───────────────┘     └──────────────┘
```

1. **User submits a creative** on the web dashboard (brand, category, ad image, headline, CTA)
2. **System reads from Databricks** — pulls persona profiles and their accumulated memories from silver tables
3. **LLM agents evaluate** — each persona sees the raw ad + their memory context and produces a structured reaction (attention, relevance, trust, desire, clarity scores + verbatim + action)
4. **Critic Agent gates quality** — checks each evaluation for persona consistency, sycophancy, and cultural authenticity; quarantines bad evals
5. **Results render on the dashboard** — scorecard, segment breakdown, verbatims, edit playbook
6. **Everything writes back to Databricks** — raw JSONs upload to DBFS, an ingest notebook processes them through bronze → silver → gold tables, and the run is logged to MLflow

### 3.2 Important Design Choice: Not Real-Time Streaming

I want to be upfront: **this is not a real-time streaming pipeline.** I'm not ingesting a live data feed from an external API.

The data flow is **request-driven batch**: a user triggers a simulation, the system reads from and writes to Databricks, and results return. This is the right pattern for creative testing — brands don't need sub-second latency, they need accurate, thorough evaluation before committing budget.

What I *do* have is:

- **Round-trip Databricks integration** — reads AND writes, not just one direction
- **Triggered micro-batch execution** — each simulation triggers an ingest job
- **Accumulating state** — persona memories grow over time, so the system gets smarter with each run
- **MLflow experiment tracking** — every run is logged for comparison

---

## 4. Multiple Data Sources

The capstone requires multiple data sources feeding a joined model. Here are mine:

| Source                     | Type                          | What It Contains                                                                                                                                                                                                       |
| -------------------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Creative Inputs**  | User-submitted (image + text) | Brand, category, headline, body copy, CTA, ad image — extracted via vision LLM into a structured CreativeCard                                                                                                         |
| **Persona Library**  | Curated JSON → Delta table   | 20 personas across 8 archetypes (aspirational buyer, brand loyalist, impulse buyer, pragmatist, price anchor, researcher, skeptic, trend follower) — each with deep demographic, psychographic, and behavioral fields |
| **Memory Streams**   | Accumulated per-persona       | Observation nodes from prior exposures, preference memories, category beliefs, reflections — stored as Delta tables, queried by scope (brand/category/full)                                                           |
| **Category Context** | Reference table               | Benchmark scores, price bands, seasonal context, competitive landscape metadata                                                                                                                                        |

These sources are joined at evaluation time: each persona evaluation combines the creative card + persona profile + relevant memories + category context into a single prompt.

---

## 5. Data Quality Controls

Quality is visible at every layer:

**Bronze → Silver validation:**

- Required creative fields present (brand, category, headline)
- Persona schema completeness (all 8 archetype fields + demographics)
- Duplicate run detection
- Invalid records routed to a `quarantine` table with rejection reason

**Evaluation quality (Critic Agent):**

- Persona consistency score (does the response match the persona's profile?)
- Sycophancy detection (is the persona being unrealistically positive?)
- Cultural authenticity (does a Lucknow persona sound like someone from Lucknow?)
- Action-reasoning alignment (does the chosen action match the given scores?)
- Evaluations scoring below threshold are quarantined with a detailed explanation

**Gold layer:**

- Aggregate scorecards only include critic-approved evaluations
- Segment breakdowns require minimum 2 personas per segment
- Run audit log tracks every decision for reproducibility

---

## 6. Agentic Actions

### Agent 1: Critic Agent (Quality Gate)

This isn't summarization — the Critic actively decides whether each evaluation enters the pipeline or gets quarantined. It reviews four dimensions and makes a PASS/FAIL determination. Failed evaluations are re-run or excluded, maintaining data integrity.

### Agent 2: Recommendation Agent (Business Decision)

Takes one of four concrete business actions based on the aggregated scorecard:

- **SCALE** — Creative is working, increase spend
- **ITERATE** — Promising foundation, specific edits recommended
- **KILL** — Fundamentally broken, pull immediately
- **SPLIT** — Strong with some segments, weak with others — create variants

Each recommendation includes confidence score, supporting evidence, risk assessment, and a prioritized edit playbook (e.g., "Change CTA to include EMI pricing" or "Add regional festival context for South India personas").

---

## 7. Medallion Pipeline Detail

### Bronze Layer

- `evaluations` — Raw persona evaluation JSONs (one row per persona-creative pair)
- `critic_verdicts` — Raw critic assessments
- `run_metadata` — Run configuration and cost tracking
- `memory_nodes` — Raw memory observations generated during the run

### Silver Layer

- `evaluations` — Validated evaluations (reasoning ≥ 10 chars, verbatim ≥ 5 chars, scores in range)
- `memory_nodes` — Validated memory nodes (node_id present, description ≥ 5 chars, persona_id valid)
- `quarantine` — Records that failed validation with rejection reasons

### Gold Layer

- `creative_scorecards` — Aggregated scores by creative (attention, relevance, trust, desire, clarity, overall grade)
- `run_audit_log` — Complete audit trail (personas used, cost, tokens, quality gate results)

### MLflow

- Each run logged as an experiment with metrics (overall score, cost, token usage, pass rate) for cross-run comparison

---

## 8. Tech Stack

| Component     | Technology                                                |
| ------------- | --------------------------------------------------------- |
| Language      | Python 3.12                                               |
| Data Models   | Pydantic v2 (structured output enforcement)               |
| LLM Providers | Anthropic Claude (evaluation + critic), OpenAI (fallback) |
| Data Platform | Databricks (Unity Catalog, Delta Lake, MLflow)            |
| Pipeline      | Medallion architecture (bronze → silver → gold)         |
| Web Dashboard | FastAPI + vanilla JS                                      |
| Testing       | pytest (120+ tests, all passing)                          |
| Deployment    | Local dev + Databricks bundle deployment                  |

---

## 9. What I Plan to Expand

This capstone is the foundation for a larger vision:

- **Long-horizon memory retrieval** — Currently using full-dump memory (leveraging 200K context windows). Future: weighted retrieval with `score = α·recency + β·relevance + γ·importance`
- **Embedding-based similarity** — Dense vector retrieval for finding relevant past exposures across categories
- **A/B variant testing** — Submit two creatives side-by-side, get a head-to-head comparison with statistical significance
- **Live API integration** — Connect to platforms like Meta Ads or Google Ads to pull real creative assets and push recommendations back
- **Regional language support** — Hinglish, Tamil, Telugu, Bengali ad copy evaluation with culturally-calibrated personas
- **Calibration loop** — Feed actual campaign outcomes back into the system to calibrate persona accuracy over time

---

## 10. Summary

Behave demonstrates:

1. **A real cloud data pipeline** — Databricks Delta tables with full medallion architecture, not just local file processing
2. **Visible data quality controls** — Validation at every layer + a Critic Agent that actively quarantines bad data
3. **Multiple data sources** — Creative inputs, persona library, memory streams, and category context joined into evaluation
4. **Agentic action beyond summarization** — Two agents making real decisions (quality gating + business recommendations)
5. **Business value** — A brand can test a creative for ~$0.25 instead of spending thousands on live A/B tests

The project uses triggered batch execution rather than real-time streaming because that matches the business use case — brands submit creatives on-demand, not continuously. What it trades in streaming velocity, it gains in evaluation depth, cultural specificity, and agentic sophistication.

I'm excited to build this and eventually expand it into a full platform for Indian D2C creative intelligence.
