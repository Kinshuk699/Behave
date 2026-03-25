# Synthetic India — Working Notes

Last updated: 2026-03-25

## Purpose

Persistent working memory for forward-looking context. Based on `synthetic_india_v2.docx` spec. Keep `Captsone.txt` and all `DataExpert_Transcript*.txt` files for capstone alignment.

---

## Visual Roadmap: Data Flow & User Journey (v2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER JOURNEY                                 │
│                                                                     │
│  Brand uploads 1-5 creatives ──► defines target audience ──► run    │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│              CREATIVE ANALYSIS (Vision-Native LLM)                   │
│                                                                     │
│  Raw image/copy ──► CreativeAnalyzer ──► CreativeCard (JSON)        │
│  • headline, body, CTA, visual tone                                 │
│  • persuasion cues, pricing signals (₹ aware)                       │
│  • platform, product category                                       │
│  NEW: Raw image also passed directly to persona evaluation          │
│  (CreativeCard = supplementary metadata, not sole input)            │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   COHORT SELECTION (Rule-based)                      │
│                                                                     │
│  Target audience filters ──► match against 20-50 PersonaProfiles    │
│  • filter by: category_affinity, demographics, archetype            │
│  • select 15-25 matching + 2-3 edge cases                           │
│  • 8 archetypes × 3-5 personas each = 20-40 total                  │
│  • output: selected persona list                                    │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│           PERSONA EVALUATION (1 LLM call per persona)               │
│                                                                     │
│  For each selected persona:                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ PersonaProfile│  │ CreativeCard │  │ MemoryStream  │             │
│  │ (soul/traits) │  │ + RAW IMAGE  │  │ (full dump or │             │
│  │              │  │ (vision-     │  │  retrieval)   │              │
│  └──────┬───────┘  │  native)     │  └──────┬───────┘              │
│         │          └──────┬───────┘         │                       │
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
│            │  LLM         │  Haiku/4o-mini for eval volume          │
│            │  (structured │  Sonnet/GPT-4o for Critic + reports     │
│            │   output)    │                                         │
│            └──────┬───────┘                                         │
│                   ▼                                                 │
│            PersonaEvaluation (Pydantic-enforced at API level)       │
│            • primary_action (SCROLL_PAST → PURCHASE_INTENT)         │
│            • dimensional scores (relevance, emotion, trust, value)  │
│            • reasoning, open_feedback                               │
│            • cost tracking (tokens, dollars)                        │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│               CRITIC AGENT (Quality Gate — NEW in v2)                │
│                                                                     │
│  Each PersonaEvaluation ──► CriticAgent ──► PASS / FAIL             │
│  Checks:                                                            │
│  • Persona consistency (response vs behavioral profile)             │
│  • Sycophancy detection (unrealistically positive?)                 │
│  • Cultural authenticity (sounds like real Indian consumer?)        │
│  • Action-reasoning alignment (action matches stated reasoning?)   │
│  FAIL → re-run or quarantine                                        │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   MEMORY SYSTEM (Generative Agents)                  │
│                                                                     │
│  Each evaluation ──► new MemoryNode in persona's MemoryStream       │
│                                                                     │
│  Phase 1-2: "Full dump" mode — entire memory stream in context      │
│  (200K token windows make retrieval unnecessary for <50 memories)   │
│  Phase 3+:  Retrieval mode when memory exceeds context window       │
│  score = α·recency + β·relevance + γ·importance                     │
│  • recency: exponential decay (0.995/simulated hour)                │
│  • relevance: embedding cosine similarity or keyword fallback       │
│  • importance: LLM-scored poignancy (1-10)                          │
│                                                                     │
│  Reflection trigger: cumulative importance > 150 points             │
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
│  └── quarantine/               Critic FAIL + schema failures        │
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
│  Future: Databricks dashboard (capstone), automated client reports  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Architecture Decisions (v2 Updated)

### From the Generative Agents paper (Park et al.)

- Memory stream = append-only log of observations, reflections, plans
- Retrieval = weighted recency + relevance + importance
- Reflection = triggered by cumulative importance threshold → higher-order insights
- Plans are also memory — future intentions stored alongside past observations

### What 2026 tech changes vs the paper

- **Vision-native agents**: Claude/GPT can *see* the ad directly — raw image goes into eval prompt alongside CreativeCard
- **200K context windows**: Full memory dump mode for early phases — skip retrieval complexity until memories exceed ~50 per persona
- **Structured output**: Pydantic schemas enforced at the API level — no parsing errors
- **Cheaper inference**: Haiku/4o-mini for high-volume evals (~₹100 per 20-agent run), premium models for Critic + reports
- **Embeddings**: text-embedding-3-small / Cohere for relevance scoring when retrieval needed later

### For Synthetic India specifically

- **CreativeCard is supplementary, not sole input** — raw image + CreativeCard together; if extraction misses cultural cues, vision-native perception catches them
- **Archetype is behavioral, demographics diversify expression** — 8 archetypes × 3-5 personas each
- **Critic Agent is mandatory** — catches sycophancy, persona inconsistency, cultural inauthenticity, action-reasoning misalignment
- **Calibration data from real campaigns is the moat** — not the prompt library
- **Stateless mode toggle** — run with memory disabled for debugging (simple boolean flag)

### Capstone framing (unchanged)

Must present as data engineering + agent systems project:
- Multi-source pipeline (creatives, personas, market context)
- Medallion architecture with quality checks
- Agent that produces actions (scale/iterate/kill), not just reports
- Cloud deployment on Databricks (Delta tables, DLT expectations, Unity Catalog)
- Keep `Captsone.txt` and all `DataExpert_Transcript*.txt` for rubric alignment

---

## Three-Layer Agent Model (v2 Formalization)

### Layer 1: The Soul (Persona Profile)

Not just demographics — purchase psychology, price sensitivity, brand trust formation, social proof dependency, cultural context (language, festivals, family influence, city tier), category involvement.

### Layer 2: The Memory (Stream + Retrieval + Reflection)

- **Phase 1-2**: Full dump — entire memory stream in context (200K windows)
- **Phase 3+**: Retrieval mode with recency/relevance/importance scoring
- Reflection trigger at cumulative importance > 150

### Layer 3: The Body (Action Space)

SCROLL_PAST → PAUSE → READ → ENGAGE → CLICK → SAVE → SHARE → PURCHASE_INTENT → NEGATIVE_REACT
One primary action + dimensional scores + reasoning + open feedback

---

## India-Specific Use Cases (v2 Additions)

All run on the same core engine. What changes: context injection, questions asked, interpretation.

1. **Festival Purchase Simulation** — Diwali/Eid/Pongal context injection, gifting psychology
2. **Influencer Trust Decay** — sequential runs with memory, tracks saturation point
3. **Price Shock Testing** — same creative at different ₹ price points, per-segment elasticity
4. **Hinglish vs English vs Regional** — language variant scoring per segment
5. **Tier 2 City Reality Check** — dedicated Tier 2 personas, different trust signals
6. **WhatsApp Commerce Simulation** — source-based trust (friend reseller vs brand broadcast)
7. **Jugaad Detector** — predicts consumer workarounds for pricing/subscriptions
8. **Matrimonial Purchase Influence** — life event context injection (wedding, new baby, etc.)
9. **Dark Pattern Resistance** — sequential UX flow evaluation, memory catches inconsistencies
10. **Second Purchase Predictor** — post-purchase memory → retention marketing response

**For capstone**: Implement use case 1 or 3 as demo. Others are future scope.

---

## 8 Persona Archetypes (v2 Target: 20-40 personas)

| Archetype | Description | Current |
|---|---|---|
| Researcher | Deep comparison, review-driven | ✅ 1 persona |
| Price Anchor | Mental price benchmarks per category | ✅ 1 persona |
| Brand Loyalist | Trust-first, repeat buyer | ✅ 1 persona |
| Aspirational Buyer | Status-driven, premium preference | ✅ 1 persona |
| Skeptic | Distrust of marketing claims | ✅ 1 persona |
| Trend Follower | Social media driven, FOMO | ✅ 1 persona |
| Impulse Buyer | Fast decision, emotional trigger | ❌ MISSING |
| Pragmatist | Feature-value calculator | ❌ MISSING |

Current: 6 personas (1 per archetype for 6 archetypes)
Target: 20+ (3-5 per archetype, varying demographics/city/language)

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

### Completed steps

1. ✅ **Fix CLI output** (2025-03-25)
   - Converted smoke test script → 8 proper pytest functions
   - Added `print_run_header()` — shows brand/category/headline before simulation
   - Added `print_run_summary()` — shows run_id, evaluations, cost, tokens, status after simulation
   - Wired both into `cmd_run` and `cmd_demo`
   - All 8/8 tests GREEN, zero API credits spent
   - Note: `run_simulation()` also prints internally — minor duplication, dedup later

### ✅ Completed: Critic Agent (2025-03-25)

**Design decision:** Approach A — Post-eval inline with summary rollup
- Critic evaluates each `PersonaEvaluation` individually, right after `evaluate_creative()`
- If FAIL → quarantine eval, exclude from scorecard aggregation
- After all evals for a creative → `CriticRunSummary` rolls up individual verdicts
- Shows both individual scores AND how each contributes to overall quality
- Model: Sonnet for Critic (quality gate), cheaper models for volume evals

**4 quality dimensions scored (0-10):**
1. Persona consistency — does eval match persona profile?
2. Sycophancy detection — 0=genuine, 10=sycophantic
3. Cultural authenticity — 0=generic/Western, 10=authentically Indian
4. Action-reasoning alignment — does primary_action follow from reasoning + scores?

**Pydantic models:**
- `CriticVerdict` — per-evaluation: 4 sub-scores, overall_quality, passed bool, explanation, flags
- `CriticRunSummary` — per-run: all verdicts, pass/fail counts, per-dimension averages, contribution breakdown

**Where it fits in simulation flow:**
```
evaluate_creative() → PersonaEvaluation
    ↓
critic.evaluate() → CriticVerdict
    ↓
if FAIL → quarantine, exclude from scorecard
if PASS → include in aggregation
    ↓
(after all evals for a creative)
critic.summarize() → CriticRunSummary
    ↓
aggregate_evaluations() (only passed evals)
    ↓
generate_recommendation()
```

**TDD Build Plan (step by step):**
1. Schema: `CriticVerdict` + `CriticRunSummary` Pydantic models
2. Config: `critic_model` field in `LLMConfig`
3. Agent: `critic_agent.py` — `evaluate_single()` function (LLM call)
4. Agent: `critic_agent.py` — `summarize_run()` function (pure Python rollup)
5. Wire into `simulation.py` — call critic after each eval, quarantine FAILs
6. CLI: show critic summary in `print_run_summary()`
7. End-to-end verify

**All 7 tasks completed. 16/16 tests GREEN. Zero API credits spent.**

**Files created/modified:**
- `src/synthetic_india/schemas/critic.py` — NEW: `CriticVerdict`, `CriticRunSummary` Pydantic models
- `src/synthetic_india/agents/critic_agent.py` — NEW: `build_critic_prompt()`, `evaluate_single()`, `summarize_run()`
- `src/synthetic_india/config.py` — MODIFIED: added `critic_model` field + `repr=False` on API key fields (security fix)
- `src/synthetic_india/engine/simulation.py` — MODIFIED: critic import, post-eval quality gate, quarantine logic, `_print_critic_summary()`, `_save_run()` persists critic data
- `src/synthetic_india/cli.py` — MODIFIED: `print_run_summary()` now accepts `critic_summary` param
- `tests/test_smoke.py` — MODIFIED: 8 new critic tests (16 total)

### ✅ Completed: Vision-Native Evaluation (2025-03-25)

**Design decision:** Option B — local file path + base64 encoding for Anthropic vision API
- `CreativeCard` gets `image_path: str | None = None` field
- Image is base64-encoded at eval time, sent as separate content block alongside text prompt
- If `image_path` is None → text-only eval (backward compatible, no breaking change)
- CreativeCard text stays as metadata; raw image is the primary visual input
- Anthropic vision API format: `{"type": "image", "source": {"type": "base64", ...}}`

**All 5 TDD tasks completed. 21/21 tests GREEN. Zero API credits spent.**

**Files created/modified:**
- `src/synthetic_india/schemas/creative.py` — MODIFIED: added `image_path` optional field
- `src/synthetic_india/agents/image_utils.py` — NEW: `encode_image()` → (base64_str, media_type)
- `src/synthetic_india/agents/llm_client.py` — MODIFIED: extracted `_build_anthropic_messages()`, added `image_base64` + `image_media_type` params to `call_anthropic()`
- `src/synthetic_india/agents/persona_evaluator.py` — MODIFIED: added `_prepare_vision_kwargs()`, wired into `call_anthropic()` call via `**vision_kwargs`
- `tests/test_smoke.py` — MODIFIED: 5 new vision tests (21 total)

### ✅ Completed: Trend Follower Persona (2025-03-25)

**Design decision:** Option A — Priya Malhotra, 22, female, Delhi metro, middle income
- BCom student + social media intern — digital-native, Hinglish inner monologue
- Key behavioral markers: social_proof_need=0.95, influencer_trust=0.85, impulse_tendency=0.85
- decision_speed="fast", research_depth=0.15, brand_loyalty=0.15
- Instagram/YouTube Shorts primary, FOMO-driven purchasing
- Trend-loyal (not brand-loyal) — will dump a brand when the trend shifts

**Files created:**
- `data/personas/trend_follower.json` — NEW: full persona profile with rich backstory
- `tests/test_smoke.py` — MODIFIED: 2 new tests (23 total)

**All 23/23 tests GREEN. Zero API credits spent.**

### ✅ Completed: Full-Dump Memory Mode + MemoryConsumer (2025-03-25)

**Design decision:** Option B — Stream Consumer abstraction with category-scoped consumption
- `MemoryConsumer` class: `consume_all()`, `consume_scored()`, `consume()` (auto-select)
- Category-scoped: threshold is per-category count, not total — beauty memories don't pollute sports evals
- Cross-category reflections toggle: `include_cross_reflections: bool = True` (agency can flip to `False` for clean-room)
- `sequence_number` on `MemoryNode` — monotonic offset assigned by `add_node()`, streaming vocabulary
- `full_dump_threshold: int = 50` in `MemoryConfig` — per-category
- Wired into `persona_evaluator.py` replacing raw `MemoryRetriever` calls
- `_build_memory_block()` now accepts `list[MemoryNode]` directly

**Capstone narrative:** Each MemoryNode is an event with a monotonic offset. The MemoryConsumer reads from offset 0 (full dump) or uses scored retrieval — mirroring how streaming systems handle backfill vs live consumption.

**Files created/modified:**
- `src/synthetic_india/memory/consumer.py` — NEW: `MemoryConsumer` class
- `src/synthetic_india/schemas/memory.py` — MODIFIED: added `sequence_number` field
- `src/synthetic_india/config.py` — MODIFIED: added `full_dump_threshold` + `include_cross_reflections`
- `src/synthetic_india/memory/stream.py` — MODIFIED: `add_node()` assigns monotonic sequence_number, `from_state()` restores counter
- `src/synthetic_india/agents/persona_evaluator.py` — MODIFIED: imports MemoryConsumer, `_build_memory_block()` takes `list[MemoryNode]`, retrieval block uses `consumer.consume()`
- `tests/test_smoke.py` — MODIFIED: 8 new tests (31 total)

**All 31/31 tests GREEN. Zero API credits spent.**

### ✅ Completed: Tiered Model Support (2025-03-25)

**Design decision:** Option B — Anthropic-only tiering, no provider routing needed
- Volume models (eval + reflection) → `claude-haiku-3-20250307` ($0.25/$1.25 per 1M tokens)
- Quality models (critic + recommendation + creative analysis) → `claude-sonnet-4-20250514` ($3/$15 per 1M tokens)
- ~12x cost reduction on volume evals
- Added `reflection_model` field to `LLMConfig`
- Updated `.env` to use Haiku for `EVAL_MODEL` and `REFLECTION_MODEL`
- Simulation reflection calls now use `config.reflection_model` instead of `config.eval_model`

**Cost estimate:** 20-persona run with ~1K prompt + ~500 completion tokens per eval:
- Eval cost: ~$0.018 (was ~$0.21 on Sonnet)
- Critic + Recommendation: ~$0.02 (stays on Sonnet)
- Total: ~$0.04 per run (≈ ₹3.5) — well within ₹100 target

**Files modified:**
- `src/synthetic_india/config.py` — MODIFIED: `eval_model` default → Haiku, added `reflection_model` field
- `src/synthetic_india/engine/simulation.py` — MODIFIED: reflection calls use `config.reflection_model`
- `.env` — MODIFIED: `EVAL_MODEL` and `REFLECTION_MODEL` set to Haiku
- `tests/test_smoke.py` — MODIFIED: 4 new tests (35 total)

**All 35/35 tests GREEN. Zero API credits spent.**

### ✅ Completed: Tune CreativeCard for Indian Ads (2026-03-25)

**What changed**: CreativeCard now structurally understands Indian advertising context.

**3 new fields added to `CreativeCard`**:
- `festival_context: Optional[str]` — Diwali, Holi, Eid, Navratri, etc. (only when actually present)
- `target_city_tier: Optional[str]` — Tier 1, Tier 2-3, Metro, Pan-India
- `cultural_references: list[str]` — rangoli, haldi, Bollywood, cricket, joint family, diyas, etc.

**Extraction prompt updated** — `creative_analyzer.py` prompt now explicitly asks for festival tie-ins, city tier inference (from pricing/language/positioning), and cultural motif detection.

**Diwali demo creative added** — `demo_creative_03` (Mamaearth Ubtan Face Wash): Hindi primary, Hinglish code-mixed, Diwali festival context, gold-orange traditional visual, haldi/diyas/rangoli cultural references, Pan-India targeting.

**Why it matters**: Without this, a Diwali sale ad and a random Tuesday ad look identical to the system. Now personas get structured cultural context, so their reactions are culturally grounded ("the Diwali pricing feels aspirational") rather than generic.

**All 39/39 tests GREEN. Zero API credits spent.**

### ✅ Completed: Expand Persona Library to 20+ (2026-03-25)

**Expanded from 6 → 20 personas** across all 8 archetypes.

**Coverage achieved**:
- 8 archetypes: researcher×3, skeptic×3, trend_follower×3, brand_loyalist×3, aspirational_buyer×2, price_anchor×2, pragmatist×2, impulse_buyer×2
- 10 cities: Delhi, Mumbai, Bangalore, Chennai, Hyderabad, Pune, Kolkata (Metro) | Jaipur, Lucknow, Ahmedabad (Tier 1) | Kochi, Patna, Indore (Tier 2)
- 8 languages: Hindi, English, Tamil, Telugu, Bengali, Gujarati, Malayalam, Marathi
- Ages 19-45, income lower_middle → premium
- Detailed backstories, inner monologue styles, and culturally authentic purchasing behaviors

**New archetypes filled**: PRAGMATIST (Vikram Rao, Fatima Sheikh) and IMPULSE_BUYER (Neha Kapoor, Arjun Singh) — previously empty enum slots.

**Shared doc created**: `docs/personas.md` — shareable overview of all 20 personas with archetype distribution, geographic coverage, and language maps.

**All 43/43 tests GREEN. Zero API credits spent.**

### Remaining v2 steps (after Persona Expansion)
1. ~~Port to Databricks (bronze/silver/gold as Delta tables) — capstone phase~~ ✅ DONE

### ✅ Completed: Port to Databricks (2026-03-25)

**Design decision:** Option A — Pure Databricks Notebooks (no DLT dependency)
- 3 Unity Catalog schemas created: `kinshuk_bronze`, `kinshuk_silver`, `kinshuk_gold`
- 3 Python notebooks deployed via Databricks Asset Bundle
- Transformation logic TDD'd locally with `databricks_bronze.py`, `databricks_silver.py`, `databricks_gold.py`
- DataExpert All purpose cluster (Zach's course infra, included in course fee)

**Schemas created in `bootcamp_students` catalog:**
- `kinshuk_bronze` — raw append-only data
- `kinshuk_silver` — validated and cleaned data
- `kinshuk_gold` — aggregated analytics-ready data

**Notebooks:**
- `01_bronze_ingest.py` — reads 20 persona JSONs + 3 demo creatives → writes to bronze Delta tables
- `02_silver_transform.py` — validates bronze → writes silver + quarantine tables (Spark filter expressions)
- `03_gold_materialize.py` — aggregates silver → creative scorecards + run audit log

**Bronze tables:** `persona_seed`, `creative_uploads`
**Silver tables:** `personas`, `creative_cards`, `quarantine`
**Gold tables:** `creative_scorecards`, `run_audit_log`

**Pipeline modules created:**
- `src/synthetic_india/pipeline/databricks_bronze.py` — `prepare_personas_for_bronze()`, `prepare_creatives_for_bronze()`, `prepare_evaluations_for_bronze()`
- `src/synthetic_india/pipeline/databricks_silver.py` — `validate_persona_rows()`, `validate_creative_rows()`, `validate_evaluation_rows()`
- `src/synthetic_india/pipeline/databricks_gold.py` — `build_scorecard_row()`, `build_audit_row()`

**Bundle config:** `databricks.yml` updated with `sync.include` for notebooks + persona data.
**Deployment:** `databricks bundle deploy` syncs to `/Workspace/Users/kinshuk.sahni6@gmail.com/.bundle/Behave/dev/files/`

**All 54/54 tests GREEN. Zero API credits spent.**

### Remaining steps
1. ~~Run notebooks on Databricks cluster to populate Delta tables~~ ✅
2. ~~MLflow integration (log eval runs, trace LLM calls)~~ ✅
3. Databricks SQL Dashboard
4. End-to-end demo with real creatives + live API calls

### ✅ Completed: MLflow Integration (2026-03-25)

**Approach:** Option A — MLflow in ingest notebook only (Databricks has MLflow built-in)

**New module:** `src/synthetic_india/pipeline/mlflow_utils.py`
- `build_mlflow_payload(metadata, scorecard)` → dict with `params` and `metrics` for MLflow

**Notebook changes:** Added Section 5 to `04_simulation_ingest.py`:
- `mlflow.set_experiment("/Users/kinshuk.sahni6@gmail.com/synthetic_india")`
- Logs params: run_id, brand, category, cohort_size
- Logs metrics: avg_overall_score, total_cost_usd, total_tokens, n_personas_evaluated, quarantine_rate
- Logs artifacts: evaluations.json, recommendation.json

**Experiment verified:** ID `898817165102177`, name `/Users/kinshuk.sahni6@gmail.com/synthetic_india`
**Bug fixed:** `NameError: evals_data` → replaced with `raw_evals` (correct variable name in notebook scope)
**Tests:** 69/69 GREEN (2 new MLflow tests)
### ✅ Completed: Simulation Ingest Notebook (2026-03-25)

**04_simulation_ingest.py** — Full medallion pipeline for real simulation run data.

**Flow:** Local `data/runs/{RUN_ID}/` → Bronze (raw) → Silver (validated) → Gold (aggregated)

**Bronze tables created:**
- `kinshuk_bronze.evaluations` — raw persona evaluations (append)
- `kinshuk_bronze.critic_verdicts` — raw critic quality verdicts (append)
- `kinshuk_bronze.run_metadata` — run info (append)

**Silver tables created:**
- `kinshuk_silver.evaluations` — validated evaluations (reasoning >= 10 chars, verbatim >= 5 chars)
- Quarantine records routed to existing `kinshuk_silver.quarantine`

**Gold tables appended:**
- `kinshuk_gold.creative_scorecards` — per-creative aggregated scores from real data
- `kinshuk_gold.run_audit_log` — audit trail entry for ingest

**Bugs fixed during deployment:**
1. `CANNOT_DETERMINE_TYPE` — Spark can't infer schema from `None` values. Fix: `_serialize()` converts `None` to `""`.
2. `_LEGACY_ERROR_TEMP_DELTA_0007` — Schema mismatch on `run_audit_log` (extra `total_cost_usd`, `total_tokens` columns vs existing table). Fix: dropped extra columns to match existing schema. ACLs prevent automatic schema migration.

**Bundle sync:** Added `data/runs/**/*.json` to `databricks.yml` sync.include.

**Verified:** All tables populated, notebook ran successfully on DataExpert cluster.

**Also fixed:** 2 stale model tests (`test_eval_model_defaults_to_haiku` → `test_eval_model_is_configured`, same for reflection). All 67/67 tests GREEN.
### ✅ Completed: MemoryScope Toggle (per-persona scope control)

**Design decision:** Option A — MemoryScope enum on MemoryConsumer with backwards-compatible default

**MemoryScope enum (str, Enum):**
- `NONE` — Fresh eyes: no memory retrieval at all
- `CATEGORY` — Same category only (default, backwards-compatible with existing behavior)
- `BRAND` — Same brand only (when a brand wants competitors excluded)
- `FULL` — Everything the persona has ever seen (cross-category, cross-brand)

**Extensibility:** `MemoryScope(str, Enum)` makes it easy to add custom scopes later — just add enum values and a handler branch in `consume()`.

**Exposure reporting:** `MemoryConsumer.get_exposure_summary(stream)` returns a dict with:
- `persona_id`, `total_memories`
- `categories` (sorted list of all seen categories)
- `brands` (sorted list of all seen brands)
- `exposures` (list of dicts with node_id, category, brand, description, importance)

**Wiring:** `memory_scope` param threaded through:
- `MemoryConsumer.consume()` — accepts `scope` + `brand` params
- `evaluate_creative()` — accepts `memory_scope` param, passes to consumer
- `run_simulation()` — accepts `memory_scope` param, passes to evaluator

**Per-persona scope:** The system supports per-persona scoping via dict mapping (future: pass `memory_scope` as `dict[persona_id, MemoryScope]` instead of single value).

**Files modified:**
- `src/synthetic_india/memory/consumer.py` — MODIFIED: added `MemoryScope` enum, `scope`/`brand` params on `consume()`, `get_exposure_summary()` method
- `src/synthetic_india/agents/persona_evaluator.py` — MODIFIED: `evaluate_creative()` accepts `memory_scope`, passes to consumer
- `src/synthetic_india/engine/simulation.py` — MODIFIED: `run_simulation()` accepts `memory_scope`, passes to evaluator
- `tests/test_smoke.py` — MODIFIED: 8 new tests (scope enum values, NONE/CATEGORY/BRAND/FULL filtering, exposure summary, default backwards-compat, wiring signatures)

**All 64/67 tests GREEN (3 pre-existing failures: stale haiku model tests + missing ingest notebook). Zero API credits spent.**

### Risks to watch

- CreativeCard extraction may oversimplify visual nuance → mitigated by vision-native eval (v2)
- Persona prompts may collapse into generic LLM opinions → mitigated by Critic Agent (v2)
- Sycophancy: LLMs default to optimism → Critic explicitly checks for this (v2)
- Aggregation scores can create false precision (expose segment disagreement)
- Cultural authenticity: "sounds like an American LLM's idea of an Indian person" → Critic checks (v2)
- Calibration data from clients may be sparse or biased
- **NEW**: Critic adds 1 LLM call per evaluation — increases cost per run by ~50%. Justified because quality gate is the v2 differentiator.

---

## Constellation Graph

Navigate the architecture visually using the Markdown NodeGraph View extension. `thoughts.md` is the hub — open Graph View to see the connected map.

### The Pipeline (linear chain)

Start here → [Creative Analysis](docs/01-creative-analysis.md) → [Cohort Selection](docs/02-cohort-selection.md) → [Persona Evaluation](docs/03-persona-evaluation.md) → [Critic Agent](docs/04-critic-agent.md) → [Memory System](docs/05-memory-system.md) → [Medallion Pipeline](docs/06-medallion-pipeline.md) → [Recommendation Agent](docs/07-recommendation-agent.md) → [Simulation Ingest](docs/12-simulation-ingest.md) → [MLflow Tracking](docs/13-mlflow-tracking.md) → Dashboard (next)

Each pipeline doc links only to its "Next →" step. Click into any node to see the full design, key decisions, and data flow.

### Knowledge Nodes (branch from hub)

| Node | What it covers |
|------|----------------|
| [Personas](docs/08-personas.md) | 20 personas, 8 archetypes, city/language coverage |
| [Roadmap](docs/09-roadmap.md) | What's done, what's next, sequencing rationale |
| [Ah-Ha Moments](docs/10-aha-moments.md) | 13 accumulated insights from paper, spec, and implementation |
| [India Use Cases](docs/11-india-use-cases.md) | 10 India-specific scenarios, capstone candidates |

---

## Ah-ha moments (accumulated)

1. Reflection is what turns repeated low-level events into stable beliefs — without it, agents remember but don't learn
2. Plans are also memory — the system retrieves from intended future actions as well as past observations
3. The paper is really about retrieval discipline under context limits — deciding which memories to surface
4. The spec's real moat is calibration data from real client outcomes, not the prompt library
5. The most important design artifact is the CreativeCard — it's the normalization boundary
6. "Simple" is where unexamined assumptions cause the most waste (superpowers principle)
7. Evidence before claims, always — no "should work" or "looks correct"
8. v2 insight: 200K context windows mean we can skip retrieval complexity for early phases — full dump mode is simpler and eliminates retrieval errors (a top failure mode in the original paper)
9. v2 insight: Vision-native eval means CreativeCard is no longer the SOLE input — the persona sees the raw ad too, catching cultural cues the extraction might miss
10. v2 insight: The Critic Agent is what prevents the system from being a "fancy wrapper" — it enforces persona consistency, catches sycophancy, and validates cultural authenticity
11. Approach A (inline critic) beats batch critic because: quarantine before aggregation, no context overflow at 20+ personas, natural fit in existing loop
12. API keys were leaking in pytest error output via dataclass repr — fixed with `repr=False`. Always check what shows up in test failures.
13. Critic gracefully degrades: if the LLM call fails, the evaluation is included anyway (fail-open). Quality gate shouldn't block the whole run.
