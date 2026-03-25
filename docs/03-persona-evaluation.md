# Persona Evaluation — The Core LLM Loop

**Status:** Built ✅
**File:** `src/synthetic_india/agents/persona_evaluator.py`

## What It Does

The atomic unit of the simulation. One persona + one creative = one `PersonaEvaluation`. This is where the LLM becomes a synthetic consumer.

## The Prompt Architecture

Each evaluation call builds a rich prompt from 4 blocks:

1. **Persona Block** — full behavioral profile: psychology, media behavior, emotional triggers, category affinities, backstory, inner monologue style
2. **Creative Block** — CreativeCard details + (v2) raw ad image via vision API
3. **Memory Block** — past experiences from the **Memory System** that shape how they react now
4. **Evaluation Instructions** — structured output format (15+ fields)

## Key Design Choices

- **Temperature 0.8** — deliberately high for diverse, authentic reactions (not polite generic ones)
- **In-character reasoning** — the persona explains *in their own voice* why they'd scroll past or click
- **Dimensional scores** — 5 dimensions (attention, relevance, trust, desire, clarity) at 0-10 each
- **Action space** — 9 possible actions from SCROLL_PAST → PURCHASE_INTENT → NEGATIVE_REACT

## After Each Evaluation

1. The evaluation goes through the **Critic Agent** quality gate
2. If PASS → included in aggregation and stored as a new memory node
3. If FAIL → quarantined, excluded from the scorecard

## Output: `PersonaEvaluation`

Defined in `src/synthetic_india/schemas/evaluation.py`:
- `primary_action`, `sentiment`, `overall_score` (0-100)
- `attention_score`, `relevance_score`, `trust_score`, `desire_score`, `clarity_score` (0-10 each)
- `first_impression`, `reasoning`, `objections[]`, `verbatim_reaction`
- `importance_score` (for memory retrieval weighting)
- `model_used`, `cost_usd`, `latency_ms` (cost tracking)

## Data Flow

```
Cohort Selection → selected personas
    +
Creative Analysis → CreativeCard + raw image
    +
Memory System → past experiences
    │
    ▼
evaluate_creative() → PersonaEvaluation
    │
    ▼
Critic Agent → PASS/FAIL quality gate
    │
    ▼
Medallion Pipeline → bronze/silver/gold
```

## Branches

- [Personas](08-personas.md) — the 8 archetypes that define who evaluates
- [Memory System](05-memory-system.md) — past experiences shape reactions

## Next →

[Critic Agent](04-critic-agent.md) — quality gate for each evaluation
