# Creative Analysis — How Ads Enter the System

**Status:** Built (needs Indian ad tuning)
**File:** `src/synthetic_india/agents/creative_analyzer.py`

## What It Does

Brand uploads a raw ad (image + copy). The `CreativeAnalyzer` agent extracts a structured `CreativeCard` from it using vision-native LLM.

## Key Insight (v2)

The CreativeCard is **supplementary, not the sole input**. In v2, the raw image is also passed directly to **Persona Evaluation**. This means if the extraction misses cultural cues (Hinglish wordplay, ₹ pricing frames, festival imagery), the persona still *sees* the original ad.

## Data Flow

```
Raw Ad (image + copy)
    │
    ▼
CreativeAnalyzer (vision LLM)
    │
    ▼
CreativeCard (Pydantic schema)
  • brand, category, headline, body_copy
  • cta_text, cta_type, price_shown
  • persuasion cues, trust signals
  • visual_style, color_dominant
    │
    ├──► Cohort Selection (category used for matching)
    └──► Persona Evaluation (card + raw image)
```

## Schema: `CreativeCard`

Defined in `src/synthetic_india/schemas/creative.py`. Key fields:
- `creative_id`, `brand`, `category`
- `headline`, `body_copy`, `cta_text`
- `price_shown`, `original_price`, `discount_percentage`
- `urgency_cues[]`, `social_proof_cues[]`, `trust_signals[]`
- `emotional_hooks[]`, `visual_style`, `language`
- `image_path` *(v2)* — optional local path to raw ad image, base64-encoded at eval time for vision-native LLM

## Next →

[Cohort Selection](02-cohort-selection.md) — matching personas to this creative's category
