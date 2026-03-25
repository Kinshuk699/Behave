# Cohort Selection — How Personas Are Chosen

**Status:** Built ✅
**File:** `src/synthetic_india/engine/cohort.py`

## What It Does

Given a product category and target audience, selects the right subset of personas from the library. Rule-based (no LLM call).

## Selection Logic

1. Match personas by `category_affinity` — personas interested in the creative's category rank higher
2. Filter by demographics if target audience specified (age range, city tier, income)
3. Select `cohort_size` personas (default 20)
4. Include 2-3 edge cases for diversity (personas who *wouldn't* normally see this ad)

## Why It Matters

- Wrong cohort = misleading results. A skincare ad tested only on beauty enthusiasts tells you nothing.
- Edge cases catch surprises — sometimes a Skeptic unexpectedly loves an ad, revealing hidden strengths.

## Data Flow

```
CreativeCard (category)
    +
Persona Library (all 20-40 personas)
    │
    ▼
select_cohort()
    │
    ▼
Selected persona list (15-25 personas)
    │
    ▼
Persona Evaluation (one LLM call per persona)
```

## Next →

[Persona Evaluation](03-persona-evaluation.md) — one LLM call per selected persona
