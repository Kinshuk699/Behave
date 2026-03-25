# Memory System — Generative Agents

**Status:** Built ✅ (retrieval mode + full-dump mode)
**Files:** `src/synthetic_india/memory/stream.py`, `src/synthetic_india/memory/retrieval.py`, `src/synthetic_india/memory/consumer.py`
**Schema:** `src/synthetic_india/schemas/memory.py`

## Why Memory Matters

Without memory, every simulation run is independent. The same persona evaluating the same brand twice would have no continuity. Memory is what turns synthetic consumers into **evolving agents**.

## From the Park et al. Paper

The Generative Agents architecture has three memory mechanisms:

### 1. Memory Stream (append-only log)
Every evaluation creates a `MemoryNode` that gets stored in the persona's stream:
- `description` — what happened ("Saw Minimalist niacinamide ad, was impressed by ingredient transparency")
- `importance` — how poignant this experience is (LLM-scored, 0-10)
- `category`, `brand` — for retrieval indexing
- `node_type` — `observation`, `reflection`, or `plan`

### 2. Retrieval (weighted scoring)
When a persona evaluates a new ad, relevant past memories are retrieved:

$$score = \alpha \cdot recency + \beta \cdot relevance + \gamma \cdot importance$$

- **Recency**: exponential decay (0.995 per simulated hour)
- **Relevance**: embedding cosine similarity or keyword fallback
- **Importance**: the raw importance score

### 3. Reflection (higher-order insights)
When cumulative importance exceeds 150 points, the persona *reflects*:
- Select focal nodes (most important recent memories)
- Generate higher-order insights ("I've been seeing a lot of serum ads — I'm becoming skeptical of the category")
- Store reflections as new memory nodes with `node_type=reflection`

## v2 Strategy: Two Phases

| Phase | When | Mode | Why |
|---|---|---|---|
| **Phase 1-2** | <50 memories per persona (per category) | **Full dump** — entire category stream in context | 200K token windows make retrieval unnecessary; eliminates retrieval errors |
| **Phase 3+** | 50+ memories (per category) | **Retrieval mode** — scored selection | Context window limits require selective memory |

### Category Scoping + Cross-Reflections

- Consumption is **category-scoped**: beauty memories don't pollute sports evals
- **Cross-category reflections** (generalized beliefs) optionally included via `include_cross_reflections` toggle
- Agency controls: `True` (default, realistic) or `False` (clean-room isolation)

## Data Flow

```
Persona Evaluation → new MemoryNode
    │
    ▼
MemoryStream.add_evaluation_memory()
    │
    ▼
Persisted to disk (JSON)
    │
    ▼
Next evaluation retrieves relevant memories
    │
    ▼
Memories shape the persona's reaction (context in prompt)
```


