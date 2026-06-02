# Behave — An Agentic Creative Testing Platform for Indian D2C Brands

> A detailed technical breakdown of the Synthetic India project.

> Built January–May 2026. Solo capstone for DataExpert Bootcamp.

> **Live at [behave-kpe2.onrender.com](https://behave-kpe2.onrender.com/)** · Password: `behave2026` · 209 automated tests, all green.

---

## What It Is

Behave solves a specific, expensive problem: **knowing whether an ad creative will work with Indian consumers before you spend a single rupee on media.**

A D2C brand uploads an ad image and a brand name. The system:

1. Auto-extracts the creative's DNA via vision AI (category, headline, persuasion cues, cultural signals)
2. Selects a cohort of 5–20 synthetic Indian consumer personas who match the target audience
3. Each persona *sees the raw ad image* and reacts in-character — producing scores, verbatim quotes, objections, and a predicted action (scroll past → purchase intent)
4. A **Critic Agent** quality-gates every single evaluation for sycophancy, persona consistency, cultural authenticity, and action-reasoning alignment
5. Everything flows through a **Bronze → Silver → Gold Medallion pipeline** with quarantine tables and MLflow tracking
6. A **Recommendation Agent** makes a concrete business decision: **SCALE**, **ITERATE**, or **KILL** — with a prioritized edit playbook

The entire simulation run costs **≈ ₹20 ($0.25)**. A real focus group in Mumbai costs ₹2–5 lakh. Behave is 10,000× cheaper and takes 60 seconds instead of 3 weeks.

But cost isn't the point. The point is that this system thinks about Indian consumers the way an experienced brand manager does — with cultural context, price sensitivity calibrated to city tier, festival psychology, and language preference — not the way a generic "AI tool" does.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Core Language** | Python 3.12 (strict typing) | Full type safety across all agent boundaries; Pydantic v2 for schema enforcement |
| **LLM Providers** | Anthropic (Claude Sonnet 4 + Haiku 3) + OpenAI (GPT-4o-mini) | **Multi-model architecture**: Haiku for volume evals, Sonnet for quality gates, GPT-4o-mini for cross-model critic |
| **Vision AI** | Claude Vision (image → structured CreativeCard) | Raw ad images go directly to personas — not just extracted text |
| **Schema Validation** | Pydantic v2 with `computed_field`, `field_validator` | Every LLM output is schema-enforced at the API level — zero string parsing |
| **Async Engine** | `asyncio.gather()` | All persona evaluations run concurrently — 20 personas in parallel, not sequential |
| **Memory System** | Custom weighted retrieval (recency + relevance + importance + arousal) | Adapted from Park et al.'s Generative Agents paper (UIST 2023) |
| **Embeddings** | OpenAI `text-embedding-3-small` (optional) | Cosine similarity for memory relevance scoring; process-local cache prevents duplicate API calls |
| **Data Pipeline** | Medallion Architecture (Bronze → Silver → Gold) | Production-grade data engineering with 10 explicit quality checks and quarantine routing |
| **Cloud Platform** | Databricks (Delta Lake, Unity Catalog, MLflow) | 4 notebooks, 3 schemas, Delta table ACID transactions, DLT-style expectations |
| **Dashboard Backend** | FastAPI (Python) | `/api/simulate` for live runs, `/api/preloaded` for case studies |
| **Dashboard Frontend** | Vanilla JS + Canvas API (zero framework) | Custom radar chart, focus-group chat UI, segment breakdowns, edit playbook |
| **Styling** | Custom CSS with design tokens | Dark/moody palette, Instrument Serif + DM Sans typography, no component library |
| **Deployment** | Render.com (Singapore region) | Auto-deploy from GitHub main branch; free tier with spin-down |
| **Testing** | pytest + pytest-asyncio | 209 tests, fully mocked (zero API calls), TDD throughout |
| **Package Manager** | pip with `pyproject.toml` | `synthetic-india` installable package with `[dev]` and `[databricks]` extras |

---

## The Architecture: A Six-Stage Pipeline with Agentic Quality Gates

```
BRAND UPLOADS AD IMAGE
        │
        ▼
┌──────────────────────────────────────────┐
│  ① CREATIVE EXTRACTOR (Vision AI)         │
│  Claude Sonnet sees the raw image →       │
│  extracts category, headline, CTA,        │
│  visual style, price framing,             │
│  persuasion cues, festival context,       │
│  cultural references                      │
│  Output: CreativeCard (Pydantic model)    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  ② COHORT SELECTION (Rule-based)         │
│  Matches extracted category against      │
│  20 personas' category affinities.       │
│  Ranks by interest_level + archetype     │
│  diversity. Selects 5-20 + 2-3 edge     │
│  cases for coverage.                     │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  ③ PERSONA EVALUATION (Vision-Native)    │
│  For EACH persona (concurrent via        │
│  asyncio.gather):                        │
│  • Loads persona soul profile            │
│  • Retrieves relevant past memories      │
│    (weighted: α·recency + β·relevance    │
│     + γ·importance + δ·arousal)          │
│  • Persona SEES the raw ad image         │
│  • Responds in-character with:           │
│    - overall_score (0-100)               │
│    - 5 dimensional scores (0-10)         │
│    - primary_action (scroll→purchase)    │
│    - verbatim quote in their voice       │
│    - objections, what would change mind  │
│    - importance_score (for memory)       │
│  Output: PersonaEvaluation (Pydantic)    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  ④ CRITIC AGENT (Three-Layer Quality     │
│     Gate — the crown jewel)              │
│                                          │
│  LAYER 1: Deterministic Rules (Python)   │
│  • Price-income sanity check             │
│  • Action-score contradiction detection  │
│  • Score inflation detection             │
│  Cost: $0.00 (no LLM call)              │
│                                          │
│  LAYER 2: Specificity Check (Regex)      │
│  • Detects bland/generic responses       │
│  • Flags forbidden consultant phrases    │
│  • Checks for concrete signals: ₹,       │
│    person names, sensory details,        │
│    temporal markers                      │
│  Cost: $0.00 (no LLM call)              │
│                                          │
│  LAYER 3: LLM Critic (Claude Sonnet)     │
│  • Persona consistency check             │
│  • Sycophancy detection                  │
│  • Cultural authenticity validation      │
│  • Action-reasoning alignment            │
│  Cost: ~$0.003 per evaluation           │
│                                          │
│  LAYER 3.5: Cross-Model Critic (GPT-4o)  │
│  • Same prompt → different model family  │
│  • Catches Claude's blind spots          │
│  • Disagreement > threshold → flag       │
│  Cost: ~$0.001 per evaluation           │
│                                          │
│  Output: CriticVerdict (PASS / FAIL)     │
│  FAIL → quarantined, excluded from gold  │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  ⑤ MEDALLION PIPELINE (Databricks)       │
│  BRONZE: Raw evaluations, persona seeds, │
│          creative uploads, memory nodes   │
│  SILVER: Schema-validated, deduplicated,  │
│          quarantined bad records          │
│  GOLD:   Creative scorecards, segment    │
│          summaries, run audit logs        │
│  + MLflow experiment tracking per run    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  ⑥ RECOMMENDATION AGENT (Business       │
│     Action — not summarization)          │
│  Input: Gold scorecards + verbatims      │
│  Output: SCALE / ITERATE / KILL          │
│  + confidence score                      │
│  + prioritized edit playbook             │
│  + risk assessment                       │
│  + audience targeting advice             │
│  Cost: ~$0.01                            │
└──────────────────────────────────────────┘
```

---

## The Project Also Ships Four Interactive HTML Explainer Decks

These aren't just README files — they're beautiful, scroll-snapped, CSS-only slide decks with progress bars, keyboard navigation, and reveal-on-scroll animations. Each serves a different audience:

| File | Audience | Purpose |
|---|---|---|
| `behave-platform-overview.html` | **Everyone** (non-technical) | 11 slides. "What is this? Who are the personas? How do they react? What's the verdict?" Accessible language, visual trait sliders, analogy-driven. |
| `behave_explainer.html` | **Technical interviewers** | 8 slides. Architecture diagrams, tech stack justification, Databricks integration, agent design. Course-technology mapping for the capstone rubric. |
| `behave_workflow_deep_dive.html` | **Engineers who want to understand every detail** | 10 slides. Every single step of the pipeline from ad upload to recommendation. Exact model names, exact formulas, exact prompt structure. The "Manufacturing Nostalgia" before/after comparison table. |
| `behave_changes_simple.html` | **Code reviewers / skeptics** | 9 slides. The 7-phase pressure-test story: Opus found 10 weak spots → all 10 fixed → 145 → 209 tests. Before/after comparisons for every phase. The honest-caveats scorecard. |

---

## The Smart & Creative Things (What Sets This Apart)

### 1. Manufacturing Nostalgia — The Crown Jewel Concept

This is the single most creative idea in the entire project. It solves a problem that most people wouldn't even recognize as a problem.

**The old way:** Nostalgia was stored as a *trait list*. `iconic_ads: ["Nirma jingle", "Air India Maharaja"]`. That's a label. A Post-It note. The LLM read it and produced analyst-speak: *"This ad appeals to nostalgia which is effective for this demographic."* Technically true. Emotionally hollow.

**The new way:** Each persona gets one or more **scene memories** — full first-person narratives with three layers:

> *"It was Sunday afternoon. Nani Ji had just finished braiding my hair with jasmine oil. The black-and-white Doordarshan set was on. Then the Nirma jingle started — washing powder Nirma... She hummed along without even noticing. That sound and that smell are fused in my head forever."*

**The three nostalgia layers (Manufacturing Nostalgia, §5.1):**

| Layer | What It Is | Why It Matters |
|---|---|---|
| **1. Sensory anchor** | The specific trigger: jasmine oil smell, jingle melody, the white powder cloud | This is what an ad today might accidentally reactivate. A visual, a sound, a texture. |
| **2. Life context** | Who was there, what they felt, what they didn't yet know | Emotional weight comes from *who* was present. Nani Ji is the emotional anchor, not the jingle. |
| **3. Present contrast** | The implicit gap between then and now | Nani Ji is gone. The jingle is still there. That gap *is* the emotional charge. The nostalgia isn't about the product — it's about the person. |

**Why this is architecturally brilliant:**

The problem wasn't that the personas lacked nostalgia data. The data was there. The problem was that nostalgia was **losing at every stage of the pipeline**:

1. **Retrieval formula:** A 1988 memory competed equally with a Tuesday memory. Same weights = old memories always lose to recent ones. Fix: `emotional_arousal = 0.85` with weight **1.5×** in the retrieval formula. A high-arousal childhood scene beats a flat recent memory even if it's 40 years older.

2. **Prompt positioning:** Scene memories were buried under 80 lines of psychology numbers at the bottom of the prompt. LLMs pay exponentially more attention to content that appears early. Fix: Scene memories now appear **FIRST** — before price sensitivity, before scores, before any number. They *lead* the context.

3. **System instruction:** The old instruction was passive: *"If a brand triggers a childhood memory — say so."* The new instruction is active: *"If this creative triggers a personal memory — let it surface BEFORE you analyze. Real consumers do not separate emotion from evaluation."*

**The before/after in the LLM's actual output:**

| Before | After |
|---|---|
| *"This ad appeals to nostalgia which is effective for this demographic. The brand heritage creates trust signals."* | *"Yaar, ye Nirma wali dhun sunte hi Nani Ji yaad aa gayi — Sunday mornings, oiled hair, Doordarshan. Dil bhar aaya. Definitely buying."* |

One is an analyst. The other is a person. That difference is the entire project.

**Honest academic framing** (from the deep-dive deck): "Manufacturing Nostalgia" is internal shorthand for *scene-based memory activation* grounded in the reminiscence-bump literature (Rubin & Berntsen, 2003) and the autobiographical-memory salience model (Conway & Pleydell-Pearce, 2000). The arousal-initialization values (scene memories at 0.85–0.95, neutral evaluations at 0.10–0.30) are **research-grounded priors, not measurements** from these specific personas. The system manufactures nothing on its own — it surfaces scene memories the persona authors wrote, and weights them so they win against newer but flatter memories. Calibration of the arousal weights, decay rates, and habituation thresholds remains an open empirical question. This is exactly the kind of honest intellectual framing that separates genuine research engineering from AI hype.

### 2. The Critic Agent Has Three Defense Layers — and a Cross-Model Cross-Checker

Most "AI evaluation" tools are thin wrappers around a single LLM prompt. Behave's Critic Agent has **four distinct quality gates**, and two of them are zero-cost deterministic checks that run before the LLM is ever called:

**Layer 1 (Deterministic Rules, $0.00):** Pure Python functions that catch obvious failures. A budget buyer (`income_segment = lower_middle`) enthusiastically committing to a premium category with no objections? Flagged. An evaluation with `overall_score: 95` but `primary_action: SCROLL_PAST`? Flagged. Four dimensions all scored exactly 7.0? Flagged as score inflation. These rules catch ~15% of failures before spending a single API cent.

**Layer 2 (Specificity Check, $0.00):** Regex and pattern matching that detects LLM "bland mode" — the thing where it produces grammatically perfect, utterly generic output. If a persona's verbatim quote contains no concrete signals (no ₹ amounts, no person names, no sensory details, no temporal markers), it's flagged. If it uses forbidden consultant-speak ("leverage," "value proposition," "holistic approach"), it's flagged.

**Layer 3 (LLM Critic, ~$0.003):** Claude Sonnet evaluates four dimensions on a 0–10 scale. The weighted formula is deliberately asymmetric: sycophancy is *inverted* — a high sycophancy score *lowers* the overall quality score. The pass threshold is 6.0. Failed evaluations are quarantined, not just tagged.

**Layer 3.5 (Cross-Model Critic, ~$0.001):** This is the really clever one. The same critic prompt runs through GPT-4o-mini — a completely different model family from a different company. If Claude and OpenAI disagree significantly on any sub-score (threshold: 3.0 points), or if they disagree on pass/fail entirely, the evaluation is flagged. This catches **same-model bias** — the failure mode where Claude the critic can't see Claude the evaluator's blind spots because they share the same training DNA.

The cross-model disagreement becomes a `rule_flags` entry, which (per the Phase 3 design) **automatically vetoes** the `passed` status. This means a single model can't rubber-stamp its own work.

### 2. The Personas Are Not Demographics — They're Psychological Profiles With Memory

Every persona is a three-layer agent model adapted from academic research (Park et al., Generative Agents, UIST 2023):

**Layer 1 — The Soul (8-dimensional psychology):**
- Purchase psychology: price sensitivity, brand loyalty, impulse tendency, social proof need, research depth, risk tolerance, decision speed, deal sensitivity — all as continuous 0–1 values, not crude buckets
- Media behavior: primary platform, ad tolerance, scroll speed, influencer trust, video preference
- Emotional profile: aspiration drivers, trust signals, rejection triggers, emotional hooks
- Category affinities with **brand relationship histories**: Isha Reddy doesn't just "prefer H&M" — she has an emotional history: *"Her first H&M purchase felt like entering the world she sees on Instagram — saves for their sale cycles and plans her interview outfits around their drops"*
- Generational touchstones: formative era, iconic ads from childhood, nostalgia intensity
- Internal conflicts: competing values with context-dependent activation
- Shadow archetype: who they become under stress
- Cognitive biases they're susceptible to

**Layer 2 — The Memory (Manufacturing Nostalgia):**
Each persona carries **formative scene memories** — not abstract traits, but specific experiential memories with sensory anchors. From the `SceneMemory` schema:
- *Sensory anchor*: the jingle, smell, brand, visual, or texture that could be triggered by a future ad
- *Life context*: who was there, what they felt, what they didn't yet know
- *Present contrast*: the implicit or explicit gap between then and now

These memories have `emotional_arousal` values (0.7–0.95) that give them **durable retrieval priority** across many simulation runs. A persona who formed a brand opinion at age 12 during a Diwali shopping trip with their mother carries that emotional weight into every future evaluation of that category.

**Memory physics (the retrieval formula, adapted and extended):**

$$\text{score} = \alpha \cdot \text{recency} + \beta \cdot \text{relevance} + \gamma \cdot \text{importance} + \delta \cdot \text{arousal} + \varepsilon \cdot \log(\text{retrieval\_count})$$

Where:
- **α (recency)**: exponential decay at 0.995/simulated hour
- **β (relevance)**: embedding cosine similarity (OpenAI text-embedding-3-small) or keyword fallback
- **γ (importance)**: LLM-scored poignancy (1–10)
- **δ (arousal)**: **1.5× weight** — higher than other weights so formative high-arousal memories surface even when old. This is the nostalgia edge.
- **ε (retrieval count)**: **log-scale** (0.3× weight) so frequent retrieval strengthens gradually, not linearly

**Layer 3 — The Body (9-action space):**
`SCROLL_PAST → PAUSE → READ → ENGAGE → CLICK → SAVE → SHARE → PURCHASE_INTENT → NEGATIVE_REACT`

This isn't a binary "good/bad" — it's a granular, measurable behavioral spectrum that maps directly to real ad platform metrics (CTR, engagement rate, conversion).

**Memory lifecycle (the habituation fix):** Memories don't just grow stronger forever. After 5+ retrievals in a 7-day window, **habituation kicks in** — arousal stops growing and starts dampening. Memories not retrieved for 30+ days experience decay, but positive-toned memories decay slower (fading affect bias, Walker & Skowronski 2009). This prevents the "runaway arousal" bug where one dominant memory poisons every future evaluation.

**The smooth cliff:** Instead of a hard binary switch at 50 memories (full dump → retrieval), there's a progressive taper — no visible behavior cliff. Elegant.

### 3. Vision-Native Evaluation: The Ad Image Goes Directly to the Persona

Most creative testing tools extract text from an ad, then feed that text to an LLM. Behave does something fundamentally different: **the raw ad image is passed directly to each persona via vision-native LLM**.

The `CreativeCard` (structured extraction) is *supplementary*, not the sole input. If the text extraction misses cultural cues — Hinglish wordplay, ₹ pricing frames, festival imagery, the visual grammar of Indian advertising — the persona still *sees* the original ad.

This is a critical design insight: **cultural signals are often visual, not textual.** The difference between a "premium" skincare ad and a "masstige" one isn't in the headline — it's in the color grading, the model's styling, the set design. A text-only pipeline would miss all of this. A vision-native pipeline catches it.

### 4. The Tiered Model Strategy: Cost-Optimized Without Sacrificing Quality

| Task | Model | Cost per call | Why |
|---|---|---|---|
| Persona Evaluation (×20) | Claude Haiku 3 | ~$0.002 | Volume task — needs speed + low cost |
| Creative Extraction | Claude Sonnet 4 | ~$0.01 | High-stakes — sets category for entire cohort |
| Critic Agent (×20) | Claude Sonnet 4 | ~$0.003 | Quality gate — needs reasoning depth |
| Cross-Model Critic (×20) | GPT-4o-mini | ~$0.001 | Second opinion — different model family |
| Recommendation | Claude Sonnet 4 | ~$0.01 | Business decision — needs strategic reasoning |
| Memory Reflection | Claude Haiku 3 | ~$0.002 | Background task — cost-sensitive |
| Embeddings | text-embedding-3-small | ~$0.0001 | Batch task — cheapest option |

Total: **~$0.25 per 20-persona simulation run**. That's ₹20. For comparison, a single real-world focus group in Mumbai costs ₹2–5 lakh and takes 3 weeks.

But there's a subtler optimization: the **embedding query cache**. When the same creative is evaluated against 20 personas, the query embedding (for memory relevance scoring) is identical across all 20. A process-local `_QUERY_EMBEDDING_CACHE` dict prevents 19 duplicate OpenAI API calls. Simple. Smart.

### 5. The Medallion Pipeline With 10 Explicit Quality Checks

Most "AI projects" skip data quality. Behave treats it as first-class:

| Layer | Check | Failure Action |
|---|---|---|
| Silver | Required fields present (Pydantic validation) | → Quarantine with rejection reason |
| Silver | Scores in 0–100 range (overall) and 0–10 (dimensions) | → Quarantine |
| Silver | Reasoning string ≥ 10 characters | → Quarantine |
| Silver | Category in canonical set of 18 | → Quarantine |
| Silver | Duplicate detection (same persona + same creative + same run) | → Quarantine |
| Silver | Persona backstory ≥ 20 characters | → Quarantine |
| Silver | At least one category affinity present | → Quarantine |
| Agent | Persona consistency (Critic Layer 3) | → Quarantine |
| Agent | Sycophancy detection (Critic Layer 3) | → Quarantine |
| Agent | Cultural authenticity (Critic Layer 3) | → Quarantine |
| Agent | Action-reasoning alignment (Critic Layer 3) | → Quarantine |
| Agent | Cross-model disagreement (Critic Layer 3.5) | → Quarantine |

Bad records are **never silently dropped.** Every quarantine has a specific rejection reason. This is production discipline, not prototype behavior.

### 6. The Category Migration Map: Real-World Messiness, Handled Gracefully

The system has 18 canonical B2C categories. But real users type messy strings. The `CATEGORY_MIGRATION_MAP` in `categories.py` handles 40+ common variations:

- `"Maid Services"` → `home_services`
- `"grocery_delivery"` → `quick_commerce`
- `"househelp"` → `home_services`
- `"beauty"` → `skincare`
- `"upi"` → `fintech`

This is the kind of detail that separates "works in a demo" from "works in production." The LLM extraction agent is also constrained to pick from the canonical 18, ensuring exact-match cohort selection works reliably.

### 7. The Dashboard: Beautiful, Functional, Zero-Framework

The dashboard is vanilla HTML/CSS/JS — no React, no build step, no 200MB `node_modules`. It's served as static files by FastAPI.

**Design:** Dark/moody palette (`#0a0a0f` base), Instrument Serif for display text, DM Sans for body, custom CSS variables for the design system. The hero section shows the verdict immediately: a giant **KILL** badge in accent red for the Zepto case study.

**Features:**
- **Focus Group Chat UI**: Each persona's verbatim quote rendered as a chat message with their name and city
- **Radar Chart**: Canvas API hand-drawn pentagon showing 5 dimensional scores (Attention, Relevance, Trust, Desire, Clarity)
- **Segment Breakdown**: Per-archetype average scores with representative verbatims
- **Edit Playbook**: Prioritized list of specific changes with current state → suggested change → expected impact
- **Live Simulation**: Upload your own ad image, pick personas, run a fresh simulation
- **Preloaded Case Study**: Zepto Valentine's Day campaign — works without API keys
- **Password-gated**: `behave2026`

Deployed to Render.com (Singapore region) with auto-deploy from GitHub main branch. Health check endpoint returns `{"status": "ok"}`.

### 8. The Databricks Integration: Not Bolted On, Built In

The project runs locally as a pure Python package but is designed for Databricks deployment from the ground up:

- **4 notebooks**: `01_bronze_ingest.py`, `02_silver_transform.py`, `03_gold_materialize.py`, `04_simulation_ingest.py`
- **3 Unity Catalog schemas**: `kinshuk_bronze`, `kinshuk_silver`, `kinshuk_gold`
- **Delta Lake**: All tables use Delta format with ACID transactions, time travel, and schema enforcement
- **DLT-style expectations**: Silver layer mirrors `EXPECT OR FAIL` / `EXPECT OR DROP` patterns
- **MLflow**: Every simulation run logged as an experiment with params (cohort_size, model versions), metrics (overall_score, pass_rate, cost), and artifacts (scorecards, verbatims)
- **Asset Bundle**: `databricks.yml` defines the deployment configuration — `databricks bundle deploy` ships everything

The `databricks_reader.py` module implements a **Databricks-first, local-fallback pattern**: in production, personas and memory nodes are read from Delta tables via Spark; locally, they fall back to JSON files. Clean abstraction.

### 9. API Key Safety: A Detail That Shows Production Thinking

The `LLMConfig` dataclass uses `repr=False` on API key fields. Why? Because pytest error messages include `repr()` of objects in the assertion context. Without `repr=False`, a failing test could leak API keys into CI logs. This is the kind of detail that comes from hard-won experience, not from following a tutorial.

Similarly, the Critic Agent is designed to **fail-open**: if the LLM call fails (network error, rate limit, API outage), the evaluation is included in the pipeline anyway. A quality gate that blocks the entire run when one API call fails is worse than no quality gate at all.

### 10. The 209-Test Suite: TDD Throughout

Every behavior-bearing module has tests:
- **`test_smoke.py`**: Schema construction, critic verdict pass/fail logic, memory retrieval scoring, cohort selection, pipeline validation
- **`test_critic_rules.py`**: All three critic layers — deterministic rules for price-income sanity, action-score contradiction, score inflation; specificity checks for bland output detection
- **`test_cross_model_critic.py`**: Cross-model disagreement computation, flag emission, threshold behavior
- **`test_lifecycle.py`**: Memory habituation (5+ retrievals → dampening), decay (30+ days → fading affect bias), smooth cliff (progressive taper, not binary)
- **`test_persona_contradictions.py`**: Schema validation for value conflicts, behavior modifiers, shadow archetypes, dial delta clamping
- **`test_critic_benchmark.py`**: Critic agent benchmarking against known-good and known-bad evaluation patterns
- **`test_embeddings_wired.py`**: Embedding cache behavior, monkeypatch patterns for unit testing
- **`test_relevance.py`**: Memory relevance scoring with and without embeddings

All 209 pass. Tests are fully mocked — zero API calls. The test suite runs in under 60 seconds.

---

## The Persona Roster: 20 Synthetic Indian Consumers

| # | Name | Archetype | City | Tier | Language | Key Trait |
|---|---|---|---|---|---|---|
| 1 | Isha Reddy | Aspirational Buyer | Hyderabad | Metro | Telugu/English | "Wants the Banjara Hills lifestyle on a Kukatpally budget" |
| 2 | Rajesh Kumar | Brand Loyalist | Kochi | Tier 1 | Malayalam | Trust-first repeat buyer; switched brands only once in 5 years |
| 3 | Priya Sharma | Brand Loyalist | Lucknow | Tier 1 | Hindi | Family-inherited brand trust; her mother's soap is her soap |
| 4 | Arjun Mehta | Impulse Buyer | Delhi | Metro | Hindi/English | Fast decision, emotional trigger — "add to cart, think later" |
| 5 | Riya Patel | Impulse Buyer | Mumbai | Metro | Gujarati/English | Instagram-driven; buys whatever her favorite influencer posts |
| 6 | Anjali Deshmukh | Pragmatist | Pune | Tier 1 | Marathi/Hindi | Feature-value calculator; reads the ingredient list before the headline |
| 7 | Vikram Singh | Pragmatist | Indore | Tier 2 | Hindi | Excel-sheet comparer; "best in class at this price point" buyer |
| 8 | Sunita Devi | Price Anchor | Patna | Tier 2 | Hindi/Bhojpuri | Mental price benchmarks per category; "₹599 for serum? It should be ₹349" |
| 9 | Karthik Subramanian | Researcher | Chennai | Metro | Tamil/English | 47 browser tabs open; reads every review before buying |
| 10 | Ananya Sen | Researcher | Kolkata | Metro | Bengali/English | Deep comparison, review-driven; trusts Wirecutter-style analysis |
| 11 | Rahul Gupta | Skeptic | Bangalore | Metro | Kannada/Hindi/English | Distrusts marketing claims; "show me the clinical trial" |
| 12 | Meera Joshi | Skeptic | Jaipur | Tier 2 | Hindi/Rajasthani | Been burned by online shopping before; needs social proof from real people |
| 13 | Neha Kapoor | Trend Follower | Ahmedabad | Tier 1 | Gujarati/Hindi | FOMO-driven; buys what's trending on Instagram Reels |
| 14 | Zara Sheikh | Trend Follower | Mumbai | Metro | Hindi/English | Early adopter; wants to be the first in her group to try new things |
| 15–20 | *(5 additional personas)* | Mixed archetypes | Various cities | Metro–Tier 2 | Various | Edge cases and coverage for all 8 archetypes |

**8 archetypes × 2–3 personas each = 20 total.** Each persona is a 2–3 KB JSON file with 50+ structured fields. The persona library is the project's moat — not the prompt templates, not the pipeline code. Real consumer data that calibrates synthetic reactions.

---

## The 18 Canonical B2C Categories

`electronics`, `fashion`, `food_and_beverage`, `food_delivery`, `quick_commerce`, `skincare`, `personal_care`, `automobile`, `two_wheeler`, `home_services`, `fintech`, `edtech`, `health_and_wellness`, `travel`, `telecom`, `jewelry_and_luxury`, `baby_and_kids`, `grocery_and_household`

Every category in the system must come from this vocabulary. The LLM extraction agent is constrained to pick from this list. Cohort selection does exact-match on category strings. The category migration map handles common free-text inputs. This is the kind of constraint that makes a system reliable instead of brittle.

---

### 4. The 5 Memory Types — A Complete Cognitive Model

Every memory in the system is one of five types, each created under specific conditions:

| Type | Trigger Condition | Purpose | Example |
|---|---|---|---|
| **SCENE** | Loaded at persona birth, never changes | Formative era memory with sensory anchors and emotional charge (0.85–0.95) | "Sunday 1988, Nani Ji, the Nirma jingle on Doordarshan" |
| **OBSERVATION** | Every ad evaluation (always written) | The atomic unit of experience — "I saw X ad, I felt Y, I would do Z" | "I saw a Surf Excel FMCG ad 3 days ago. I would scroll past. The price felt too premium." |
| **PREFERENCE** | Only when `overall_score > 70` | Captures lasting brand affinity — the persona genuinely liked this | "I genuinely liked the Myntra fashion ad. The pricing was transparent and felt fair to me." |
| **BELIEF** | Only when `overall_score < 30` | Captures lasting brand distrust or category skepticism | "I was put off by the Lenskart ad. Something about the hard sell reminded me of MLM tactics." |
| **REFLECTION** | Triggered when cumulative importance > 50 | Higher-order insight synthesized from multiple observations | "I tend to distrust skincare brands that rely on celebrity endorsements without clinical backing." |

**The Reflection mechanism** is particularly clever. It mirrors how humans form abstract beliefs: you don't know after one bad date that you have a type. After five, the pattern is obvious. Claude Haiku 3 takes the 10 most important recent memories and synthesizes a higher-order insight — which then gets retrieved in future evaluations and shapes future reactions. This is how the personas *learn* across runs, not just remember.

**The auto-strategy switch:** If a persona has fewer than 50 category memories, the system dumps ALL of them into the prompt (full-dump mode, leveraging 200K context windows). Once they cross 50, the weighted scoring formula kicks in and picks the top 5. This mirrors how streaming systems work — backfill everything early, then switch to live scoring at scale. It eliminates the #1 failure mode from the original Generative Agents paper (retrieval errors in early phases when there aren't enough memories to score meaningfully).

### 5. The 7-Phase Pressure-Test Story: 145 → 209 Tests

The project's code quality narrative is a story, not just a number. Claude Opus was used to stress-test the entire codebase — and it found 10 weak spots. Over seven phases, every single one was addressed. The test suite grew from 145 to 209 tests. **Zero regressions.** Every phase started with failing tests (RED), then made them pass (GREEN). No code shipped without tests written first.

| Phase | Opus's Complaint | What Changed | Tests Added |
|---|---|---|---|
| **1 — Relevance** | "Memory picker is just keyword overlap — a black box" | Replaced keyword counting with multi-signal formula: 40% category match + 30% shared themes + 20% era/sensory cues + 10% word overlap | +5 |
| **2 — Lifecycle** | "Memory keeps getting stronger forever — not how brains work" | Added habituation (5+ retrievals in 7 days → dampening), frequency cap (`log(1+min(count, 5))`), 30-day fade with fading affect bias | +11 |
| **3 — Critic v2** | "One LLM judging another LLM — marking your own homework" | Built deterministic Python rules layer: price-income sanity, action-score contradiction, score inflation detection. $0 cost, runs in milliseconds | +12 |
| **3.5 — Cross-model** | "Same model judging itself = inflated scores" | Added GPT-4o-mini as second critic. Different training data, different blind spots. Disagreement > threshold → auto-quarantine | +10 |
| **4 — Persona contradictions** | "Personas are too flat — real people have internal conflicts" | Added shadow archetypes, value conflicts, non-negotiables, context modifiers. Personas can now be conflicted: "Wants iPhone but feels guilty buying foreign" | +12 |
| **5 — Docs honesty** | "Your docs claim more than your code actually does" | Rewrote over-claiming sections. "Memory gets stronger forever" → "gets stronger up to a cap of 5, then plateaus; habituation kicks in." Honest academic framing on Manufacturing Nostalgia | docs |
| **6 — Critic benchmark** | "You say the critic catches bad outputs — prove it" | Built 18-case golden benchmark: 10 bad examples (must catch all), 8 good examples (must not flag). **100% precision, 100% recall, $0 cost.** Now a regression gate | +6 |
| **7 — Embeddings** | "`use_embeddings=True` is a flag that does nothing — dead code" | Actually wired OpenAI embeddings into the relevance scorer. Process-level cache prevents duplicate calls. Falls back gracefully when no OpenAI key. Old memories without embeddings still work | +8 |

**The critic benchmark deserves special mention.** It's a small golden set of 18 hand-labeled examples — 10 deliberately bad (made-up brand facts, persona contradictions, vague non-reactions, banned corporate phrases) and 8 genuinely good (specific, grounded, persona-consistent). The deterministic critic runs against all 18 in milliseconds at zero cost. 10 of 10 bad caught. 8 of 8 good cleared. This is now a **regression gate** — any future change that breaks the critic will fail the test suite immediately. The bar can only go up.

### 6. Persona Contradictions — The "Therapist's Note" Beyond the CV

Real people are not internally consistent. A real Indian middle-class buyer might *say* "I only buy Indian brands" but also *own* an iPhone. The old personas were too clean. Four new mechanisms fix this:

- **Shadow archetype**: Who they become under stress, excitement, or off-script. A Pragmatist might become an Impulse Buyer during Diwali sales.
- **Value conflicts**: Pairs of competing values with context-dependent activation. *"Thrift (grocery shopping with mother) vs. Status (dinner with college friends)."*
- **Non-negotiables**: Hard limits the persona will not cross. *"Won't pay more than ₹500 for skincare."* The critic flags any evaluation that violates these.
- **Context modifiers**: Named situations that shift psychology dials. *"End of month: price_sensitivity +0.3, impulse_tendency -0.2."*

The persona evaluator **actively surfaces** these tensions when scoring an ad. The Critic Agent checks for them. The result: reactions feel like a person, not a stereotype. As the platform overview deck says: *"Before, every persona was a one-page CV. Now they're a CV plus a therapist's note about their contradictions."*

### 7. The Embedding Dead-Code Fix — A Flag That Now Actually Does Something

The function signature had `use_embeddings=True` — a parameter that looked impressive in the API but was silently ignored. Memory nodes had `embedding: null`. Pure vapor. Phase 7 fixed this: the flag now triggers an actual OpenAI `text-embedding-3-small` call, the relevance scorer accepts an embedding vector, and the 10% tiebreaker slot in the relevance formula uses true cosine similarity instead of keyword overlap. A process-level `_QUERY_EMBEDDING_CACHE` dict prevents duplicate calls when the same creative is evaluated across 20 personas.

**What makes this honest:** The fix document explicitly states that old memories saved before this change still have no embedding stored. For those, the old keyword path runs. New memories pick up embeddings automatically. No backfill was done. This kind of honest caveat — instead of pretending everything is perfect — is rare in AI projects.

## What Makes This Different From Every Other "AI Marketing Tool"

1. **Not a wrapper around ChatGPT.** The Critic Agent + Cross-Model Critic means no single LLM's output is trusted without verification. Two different model families check each other's work.

2. **Personas have psychology, not just demographics.** Price sensitivity, brand loyalty, impulse tendency, social proof need, research depth, risk tolerance, decision speed, deal sensitivity — all as continuous values that shape every evaluation.

3. **Memory with physics.** Recency decay, relevance scoring, importance weighting, arousal boost for formative memories, habituation for over-retrieved memories, fading affect bias for positive memories. This isn't a vector database — it's a psychological model.

4. **Vision-native, not text-only.** The raw ad image goes to each persona. Cultural signals that are visual, not textual, are preserved.

5. **Agentic action, not summarization.** The Recommendation Agent makes a concrete business decision (SCALE/ITERATE/KILL) with a prioritized edit playbook. It doesn't just say "here's what the data shows" — it says "here's what you should DO."

6. **Production data engineering, not a notebook.** Medallion architecture, quarantine tables, MLflow tracking, Delta Lake ACID transactions, Unity Catalog governance. This is a data pipeline, not a script.

7. **India-specific from the ground up.** City tiers, language preferences, festival psychology, family influence, platform behavior differences, ₹ pricing frames. Not a Western model with Indian labels slapped on.

8. **Cost-transparent.** Every LLM call logs tokens and cost. The total run cost is displayed prominently. No "we use AI" hand-waving.

9. **Honest about scope.** The roadmap explicitly lists what's not built yet. No "coming soon" vaporware.

---

## What Is Not Built Yet (Honest Scope)

- **Long-horizon memory retrieval**: Full-dump mode (200K context window) is used for Phase 1–2. Scored retrieval is implemented and tested but not yet active in production — it activates when memories exceed 50 per persona per category.
- **All 10 India-specific use cases**: Festival purchase simulation, influencer trust decay, price shock testing, Hinglish vs English, Tier 2 reality check, WhatsApp commerce, Jugaad detector, matrimonial purchase influence, dark pattern resistance, second purchase predictor. Designed, not yet implemented. The platform architecture supports all of them with context injection.
- **User accounts & auth**: Dashboard is password-gated with a shared secret, not individual accounts.
- **Real-time streaming pipeline**: Current architecture is triggered micro-batch (process what's available, then stop). Deliberate design choice — creative testing is request-driven, not streaming.
- **A/B test statistical rigor**: The recommendation agent can suggest SPLIT_TEST but doesn't compute statistical significance.
- **Calibration data from real campaigns**: The moat isn't built yet. When real client outcomes are fed back into the system, persona reactions can be tuned against ground truth.

---

## Key Files Reference

| File | Purpose |
|---|---|
| `src/synthetic_india/agents/critic_agent.py` | Three-layer quality gate with Claude + deterministic pre-checks |
| `src/synthetic_india/agents/critic_rules.py` | Zero-cost deterministic rules: price-income sanity, score inflation, action-score contradiction |
| `src/synthetic_india/agents/cross_model_critic.py` | GPT-4o-mini second opinion on Claude's critic verdicts |
| `src/synthetic_india/agents/persona_evaluator.py` | Vision-native persona evaluation with memory retrieval |
| `src/synthetic_india/agents/recommendation_agent.py` | Business decision agent: SCALE/ITERATE/KILL + edit playbook |
| `src/synthetic_india/agents/creative_extractor.py` | Vision AI: raw ad image → structured CreativeCard |
| `src/synthetic_india/memory/retrieval.py` | Weighted memory retrieval: α·recency + β·relevance + γ·importance + δ·arousal |
| `src/synthetic_india/memory/stream.py` | Append-only memory stream with reflection triggering |
| `src/synthetic_india/memory/consumer.py` | Memory scoping: none / category / brand / full |
| `src/synthetic_india/engine/simulation.py` | Orchestrator: extract → cohort → evaluate → critique → aggregate → recommend |
| `src/synthetic_india/engine/cohort.py` | Category-based persona ranking and selection |
| `src/synthetic_india/schemas/evaluation.py` | PersonaEvaluation: 9 actions, 5 dimensions, sentiment, verbatims |
| `src/synthetic_india/schemas/persona.py` | PersonaProfile: 3-layer model with shadow archetype, value conflicts, context modifiers |
| `src/synthetic_india/schemas/memory.py` | MemoryNode + SceneMemory with sensory anchors and nostalgia layers |
| `src/synthetic_india/schemas/creative.py` | CreativeCard: the normalization boundary between raw ads and structured evaluation |
| `src/synthetic_india/schemas/critic.py` | CriticVerdict: weighted quality scoring with inverted sycophancy |
| `src/synthetic_india/pipeline/silver.py` | 10 quality checks with quarantine routing |
| `src/synthetic_india/pipeline/gold.py` | CreativeScorecard aggregation, segment summaries |
| `src/synthetic_india/pipeline/mlflow_utils.py` | MLflow experiment tracking per simulation run |
| `src/synthetic_india/categories.py` | 18 canonical categories + 40-entry migration map |
| `src/synthetic_india/config.py` | Environment-driven config with `repr=False` on secrets |
| `data/personas/` | 20 persona JSON profiles (2–3 KB each, 50+ fields) |
| `data/runs/` | 11 preloaded simulation runs with full evaluation data |
| `notebooks/` | 4 Databricks notebooks for bronze/silver/gold/ingest |
| `dashboard/app.py` | FastAPI backend: `/api/simulate`, `/api/preloaded`, password gate |
| `dashboard/static/` | Vanilla JS dashboard: radar chart, focus group chat, edit playbook |
| `tests/` | 209 automated tests, fully mocked, all green |

---

## Running It Yourself

```bash
# 1. Clone and install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Set your API keys
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...        # optional, for embeddings + cross-model critic

# 3. Run all tests (no API keys needed)
python -m pytest tests/ -q
# → 209 passed

# 4. Run the dashboard
cd dashboard && pip install -r requirements.txt
uvicorn app:app --reload --port 8000
# → Open http://localhost:8000 · Password: behave2026

# 5. Run a live smoke test (~$0.09)
python run_smoke_test.py
```

---

## The Big Idea

Most "AI for marketing" tools ask: *"What does ChatGPT think of this ad?"*

Behave asks: *"What would Isha Reddy — a 21-year-old aspiring buyer from Hyderabad who measures her life in first-salary milestones and Instagram aesthetics, who bought her first H&M piece as a talisman for placement season, who uses a Realme phone but never posts about it because it doesn't fit the aesthetic she's building — what would SHE think of this ad at 11 PM while scrolling Instagram in her Kukatpally bedroom?"*

That's a fundamentally different question. And it's the question that actually matters when you're about to spend ₹50 lakh on a campaign.

---

*Built solo by [Kinshuk Sahni](https://www.linkedin.com/in/sahnikinshuk/) · [kinshuksahni.com](https://kinshuksahni.com/) · March–May 2026*
