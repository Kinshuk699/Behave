# Critic Agent — Quality Gate (v2)

**Status:** ✅ Built (2025-03-25) — 16/16 tests GREEN
**File:** `src/synthetic_india/agents/critic_agent.py`
**Schema:** `src/synthetic_india/schemas/critic.py`

## Why It Exists

LLMs are sycophantic by default. Without a quality gate, every persona would give every ad a glowing review. The Critic Agent is what prevents Synthetic India from being a "fancy wrapper around ChatGPT."

## What It Checks (4 dimensions, 0-10 each)

| Dimension | What It Catches | Example |
|---|---|---|
| **Persona Consistency** | Response doesn't match behavioral profile | A Skeptic giving all 8+ scores with no objections |
| **Sycophancy Score** | Unrealistically positive evaluation | Generic praise, no real objections, suspiciously high scores |
| **Cultural Authenticity** | Sounds like a real Indian consumer | Not "American LLM playing Indian" — checks for grounded cultural refs |
| **Action-Reasoning Alignment** | Action follows from stated reasoning | Low trust_score (3/10) but primary_action is "purchase_intent" → fail |

## Design Decision: Inline (Approach A)

The critic runs **immediately after each** persona evaluation, not as a batch:
- Quarantines bad evals **before** they pollute the scorecard
- No context overflow risk at 20+ personas
- Natural fit in the existing simulation loop
- If the critic LLM call fails → evaluation included anyway (fail-open)

## Scoring

```
overall_quality = 0.30 × persona_consistency
                + 0.25 × (10 - sycophancy_score)    ← inverted: high syco = bad
                + 0.25 × cultural_authenticity
                + 0.20 × action_reasoning_alignment

PASS threshold: overall_quality >= 6.0
```

## Output: Individual + Combined

- **Per-evaluation:** `CriticVerdict` — 4 sub-scores, overall_quality, passed bool, explanation, flags
- **Per-run:** `CriticRunSummary` — all verdicts, pass/fail counts, per-dimension averages, quality contribution breakdown (how each persona's score affects the total)

## Data Flow

```
Persona Evaluation → PersonaEvaluation
    │
    ▼
critic_agent.evaluate_single() → CriticVerdict
    │
    ├── PASS → include in Medallion Pipeline aggregation
    └── FAIL → quarantine, exclude from scorecard
    │
    ▼
critic_agent.summarize_run() → CriticRunSummary
    │
    ▼
Recommendation Agent (only sees passed evals)
```

## Next →

[Medallion Pipeline](06-medallion-pipeline.md) — passed evals flow to silver/gold, failed to quarantine
