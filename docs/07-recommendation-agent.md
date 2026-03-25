# Recommendation Agent — Agentic Decisions

**Status:** Built ✅
**File:** `src/synthetic_india/agents/recommendation_agent.py`
**Schema:** `src/synthetic_india/schemas/recommendation.py`

## What It Does

This is NOT a summarizer. It's a **decision engine** that commits to a specific action with business reasoning. It takes gold-layer scorecards and tells the brand what to do.

## The 5 Actions

| Action | When | Example |
|---|---|---|
| **SCALE** | Creative performing well across segments | "This ad resonates with 4/5 archetypes. Increase spend." |
| **ITERATE** | Promising but needs specific edits | "Trust scores low among Skeptics. Add clinical evidence." |
| **KILL** | Not resonating, wasting spend | "Overall score 32/100. Pull this creative." |
| **SPLIT_TEST** | Results too close to call | "Creative A and B within 5 points. Run A/B." |
| **HOLD** | Insufficient data | "Only 3 evaluations completed. Need more data." |

## Key Design Choices

- **Temperature 0.4** — lower than evaluation (0.8) because we want more consistent, structured decisions
- **Non-hedging** — the system prompt explicitly says "make non-hedging decisions"
- **Edit suggestions** — when ITERATE, generates specific `EditRecommendation` items (element, current_state, suggested_change, expected_impact, priority)

## Output: `AgentRecommendation`

- `winning_creative_id`, `recommended_action`, `confidence_score` (0-1)
- `reasoning_summary`, `key_evidence[]`
- `top_risks[]`, `risk_level` (low/medium/high)
- `edit_recommendations[]` — specific changes to make
- `strongest_segment`, `weakest_segment` — which archetypes loved/hated it
- `creative_ranking[]`, `comparative_analysis` — when multiple creatives tested

## Data Flow

```
Medallion Pipeline → Gold scorecards
    │
    ▼
generate_recommendation() → AgentRecommendation
    │
    ▼
Output to user (CLI + saved as recommendation.json)
```


