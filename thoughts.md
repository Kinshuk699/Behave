# Synthetic India — Working Notes

Last updated: 2025-07-26

## Purpose

Persistent working memory for forward-looking context. Research deep-dives have been absorbed into code and `capstone_roadmap.md` — this file keeps only what matters for current and future work.

---

## Visual Roadmap: Data Flow & User Journey

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER JOURNEY                                 │
│                                                                     │
│  Brand uploads 1-5 creatives ──► defines target audience ──► run    │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   CREATIVE ANALYSIS (Vision LLM)                    │
│                                                                     │
│  Raw image/copy ──► CreativeAnalyzer ──► CreativeCard (JSON)        │
│  • headline, body, CTA, visual tone                                 │
│  • persuasion cues, pricing signals                                 │
│  • platform, product category                                       │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   COHORT SELECTION (Rule-based)                      │
│                                                                     │
│  Target audience filters ──► match against 5-50 PersonaProfiles     │
│  • filter by: category_affinity, demographics, archetype            │
│  • select 15-25 matching + 2-3 edge cases                           │
│  • output: selected persona list                                    │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│               PERSONA EVALUATION (1 LLM call per persona)           │
│                                                                     │
│  For each selected persona:                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ PersonaProfile│  │ CreativeCard │  │MemoryRetriever│             │
│  │ (soul/traits) │  │ (normalized  │  │ (past brand + │             │
│  │              │  │  ad data)    │  │  category     │              │
│  └──────┬───────┘  └──────┬───────┘  │  memories)   │              │
│         │                 │          └──────┬───────┘               │
│         └─────────┬───────┘                 │                       │
│                   ▼                         │                       │
│            ┌──────────────┐                 │                       │
│            │   PROMPT      │◄───────────────┘                       │
│            │ persona block │                                        │
│            │ creative block│                                        │
│            │ memory block  │                                        │
│            └──────┬───────┘                                         │
│                   ▼                                                 │
│            ┌──────────────┐                                         │
│            │  LLM (Claude │                                         │
│            │  Sonnet 4)   │                                         │
│            └──────┬───────┘                                         │
│                   ▼                                                 │
│            PersonaEvaluation                                        │
│            • primary_action (SCROLL_PAST → PURCHASE_INTENT)         │
│            • dimensional scores (relevance, emotion, trust, value)  │
│            • reasoning, open_feedback                               │
│            • cost tracking (tokens, dollars)                        │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   MEMORY SYSTEM (Generative Agents)                  │
│                                                                     │
│  Each evaluation ──► new MemoryNode in persona's MemoryStream       │
│                                                                     │
│  score = α·recency + β·relevance + γ·importance                     │
│  • recency: exponential decay over hours                            │
│  • relevance: cosine similarity (embeddings) or keyword fallback    │
│  • importance: LLM-scored poignancy (0-10, normalized)              │
│                                                                     │
│  Reflection trigger: cumulative importance > 150 points             │
│  • generates higher-order insights from raw memories                │
│  • e.g. "I've been disappointed by skincare brands making           │
│         exaggerated claims" (from 5+ individual ad evaluations)     │
│                                                                     │
│  Memories persist across runs → personas evolve over time           │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   MEDALLION PIPELINE                                 │
│                                                                     │
│  BRONZE (raw, append-only)                                          │
│  ├── creative_uploads/     raw ad data + creative cards             │
│  ├── persona_evaluations/  raw LLM outputs per persona             │
│  ├── memory_streams/       raw memory nodes per persona             │
│  └── run_metadata/         timestamps, costs, cohort info           │
│                                                                     │
│  SILVER (validated, quarantined)                                     │
│  ├── validated_personas        Pydantic-checked profiles            │
│  ├── validated_evaluations     schema-conforming evaluations        │
│  ├── validated_memories        well-formed memory nodes             │
│  └── quarantine/               rows that failed validation          │
│                                                                     │
│  GOLD (aggregated, analytics-ready)                                  │
│  ├── creative_scorecards       per-creative aggregate metrics       │
│  ├── segment_summaries         per-archetype roll-ups               │
│  ├── memory_analytics          retrieval stats, reflection rates    │
│  └── run_summaries             cost, persona count, timing          │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│               RECOMMENDATION AGENT (Agentic Action)                  │
│                                                                     │
│  Gold metrics ──► RecommendationAgent (LLM) ──► decision:           │
│  • SCALE: creative is performing well, increase spend               │
│  • ITERATE: promising but needs specific edits                      │
│  • KILL: not resonating, stop spend                                 │
│  • SPLIT_TEST: unclear, needs A/B testing                           │
│  • HOLD: insufficient data                                          │
│                                                                     │
│  Output: AgentRecommendation with reasoning + edit suggestions      │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        OUTPUT TO USER                                │
│                                                                     │
│  CreativeScorecard (per creative):                                   │
│  • overall_score (1-100)                                            │
│  • action distribution (how many scroll, pause, engage, etc.)       │
│  • segment breakdown (by archetype)                                 │
│  • top themes and sentiment                                         │
│  • recommended_action + reasoning                                   │
│  • total cost for the run                                           │
│                                                                     │
│  Future: Databricks dashboard, automated client reports             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Architecture Decisions

### From the Generative Agents paper (Park et al.)

- Memory stream = append-only log of observations, reflections, preferences
- Retrieval = weighted recency + relevance + importance
- Reflection = triggered by cumulative importance threshold, produces higher-order insights
- Plans are also memory — future intentions are stored alongside past observations

### For Synthetic India specifically

- **Phase 1 is stateless per-run** but memory persists across runs (this is where long-horizon value lives)
- **CreativeCard is the normalization boundary** — if extraction is lossy, all downstream judgments degrade
- **Archetype is behavioral, demographics diversify expression** — stronger than demographics-first persona design
- **Calibration data from real campaigns is the moat** — not the prompt library

### Capstone framing

Must present as data engineering + agent systems project:
- Multi-source pipeline (creatives, personas, market context)
- Medallion architecture with quality checks
- Agent that produces actions (scale/iterate/kill), not just reports
- Cloud deployment on Databricks (Delta tables, DLT expectations, Unity Catalog)

---

## Current State & What's Next

### Built (needs review)

- All Pydantic schemas (persona, creative, evaluation, memory, recommendation)
- Memory system (stream + retrieval + reflection)
- 3 agents (creative analyzer, persona evaluator, recommendation)
- Simulation engine with cohort selection
- Medallion pipeline (bronze/silver/gold)
- CLI (demo + run commands)
- 5 starter personas
- Smoke test passes

### Next steps

1. Review all code for errors (step by step, one module at a time)
2. Set up `.env` with real API keys and run first real simulation
3. Tune prompts based on evaluation quality
4. Add embeddings for memory retrieval accuracy
5. Run multiple simulations to test memory accumulation
6. Port to Databricks (bronze/silver/gold as Delta tables)
7. Build DLT quality expectations for silver layer
8. Expand persona library to 15-20 after first 5 proven

### Risks to watch

- Creative-card extraction may oversimplify visual nuance
- Persona prompts may collapse into generic LLM opinions (test for distinctiveness)
- Aggregation scores can create false precision (expose segment disagreement)
- Poor cohort selection will look like model failure
- Calibration data from clients may be sparse or biased

---

## Ah-ha moments (accumulated)

1. Reflection is what turns repeated low-level events into stable beliefs — without it, agents remember but don't learn
2. Plans are also memory — the system retrieves from intended future actions as well as past observations
3. The paper is really about retrieval discipline under context limits — deciding which memories to surface
4. The spec's real moat is calibration data from real client outcomes, not the prompt library
5. The most important design artifact is the CreativeCard — it's the normalization boundary
6. "Simple" is where unexamined assumptions cause the most waste (superpowers principle)
7. Evidence before claims, always — no "should work" or "looks correct"
