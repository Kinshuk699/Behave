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
| Trend Follower | Social media driven, FOMO | ❌ MISSING — add next |
| Impulse Buyer | Fast decision, emotional trigger | ❌ MISSING |
| Pragmatist | Feature-value calculator | ❌ MISSING |

Current: 5 personas (1 per archetype for 5 archetypes)
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

### Next steps (from v2 spec, engineer priorities)

1. **Review all code** for errors (step by step, one module at a time)
2. **Add stateless mode toggle** — boolean flag to disable memory for debugging
3. **Add vision-native evaluation** — send raw ad image alongside CreativeCard to each persona
4. **Implement Critic Agent** — persona consistency + sycophancy + cultural authenticity + action-reasoning checks
5. **Tune CreativeCard extraction for Indian ads** — test with real Hinglish copy, ₹ pricing, cultural refs
6. **Add Trend Follower persona** — critical missing archetype for Indian D2C
7. **Set up `.env` with real API keys** and run 3 real Indian D2C ads through the system
8. **Skip Databricks for now** — focus on simulation quality first; Databricks is for capstone later
9. Port to Databricks (bronze/silver/gold as Delta tables) — capstone phase
10. Expand persona library to 20+ after first 5-8 proven

### Risks to watch

- CreativeCard extraction may oversimplify visual nuance → mitigated by vision-native eval (v2)
- Persona prompts may collapse into generic LLM opinions → mitigated by Critic Agent (v2)
- Sycophancy: LLMs default to optimism → Critic explicitly checks for this (v2)
- Aggregation scores can create false precision (expose segment disagreement)
- Cultural authenticity: "sounds like an American LLM's idea of an Indian person" → Critic checks (v2)
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
8. v2 insight: 200K context windows mean we can skip retrieval complexity for early phases — full dump mode is simpler and eliminates retrieval errors (a top failure mode in the original paper)
9. v2 insight: Vision-native eval means CreativeCard is no longer the SOLE input — the persona sees the raw ad too, catching cultural cues the extraction might miss
10. v2 insight: The Critic Agent is what prevents the system from being a "fancy wrapper" — it enforces persona consistency, catches sycophancy, and validates cultural authenticity
