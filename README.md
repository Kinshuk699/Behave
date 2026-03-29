# Behave — Capstone Submission

**Kinshuk Sahni · DataExpert Bootcamp · March 2026**

An agentic creative testing platform that simulates how real Indian consumers react to ad creatives — before a single rupee is spent.

---

## Quick Start

### 1. Prerequisites

- Python 3.10+ (tested on 3.12)
- An **Anthropic API key** (required — Claude Sonnet 4 powers all agents)
- An **OpenAI API key** (optional — only used for embeddings if enabled)

### 2. Install

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -e ".[dev]"
```

### 3. Set Environment Variables

Create a `.env` file in the project root (or export directly):

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...your-key-here...

# Optional (for embeddings)
OPENAI_API_KEY=sk-...your-key-here...

# Optional (for Databricks pipeline — only needed if running notebooks)
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...your-token-here...
DATABRICKS_CLUSTER_ID=your-cluster-id
```

> **You must supply your own API keys.** The project does not ship with any keys.

### 4. Run Tests (no API keys needed)

```bash
python -m pytest tests/test_smoke.py -q
```

All 135 tests should pass. Tests are fully mocked — no live LLM calls.

### 5. Run the Dashboard

```bash
cd dashboard
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

**Dashboard password: `behave2026`**

The dashboard has a **Preloaded Case Study** (Zepto quick commerce campaign) that works without API keys — click "Load Preloaded Run" to see the full output instantly.

To run a **live simulation**, you need a valid `ANTHROPIC_API_KEY` set in your environment.

---

## What's in This Zip

| File/Folder | Description |
|-------------|-------------|
| `README.md` | This file — setup and run instructions |
| `capstone_submission.md` | Full capstone writeup with course technology mapping |
| `behave_explainer.html` | Visual 8-slide project explainer (open in browser) |
| `Behaveeee.mp4` | Live demo recording of the project |
| `src/synthetic_india/` | All application code (agents, engine, pipeline, schemas, memory) |
| `dashboard/` | FastAPI dashboard (app.py + static frontend) |
| `data/personas/` | 20 persona JSON profiles |
| `data/runs/` | Preloaded simulation run data |
| `data/memory/` | Persona memory streams |
| `notebooks/` | Databricks notebooks (bronze/silver/gold/ingest) |
| `tests/` | 135 automated tests |
| `docs/` | Design documentation |
| `pyproject.toml` | Python project config + dependencies |
| `databricks.yml` | Databricks Asset Bundle config |
| `capstone_roadmap.md` | Project roadmap and architecture decisions |
| `thoughts.md` | Working notes and session history |

---

## Environment Variables Reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | **Yes** (for live sims) | — | Powers all LLM agents (Claude Sonnet 4) |
| `OPENAI_API_KEY` | No | — | Embeddings (text-embedding-3-small) |
| `EVAL_MODEL` | No | `claude-haiku-3-20250307` | Model for persona evaluations |
| `CREATIVE_ANALYSIS_MODEL` | No | `claude-sonnet-4-20250514` | Model for creative extraction |
| `RECOMMENDATION_MODEL` | No | `claude-sonnet-4-20250514` | Model for recommendation agent |
| `CRITIC_MODEL` | No | `claude-sonnet-4-20250514` | Model for critic agent |
| `DATABRICKS_HOST` | No | — | Databricks workspace URL |
| `DATABRICKS_TOKEN` | No | — | Databricks PAT |
| `DATABRICKS_CLUSTER_ID` | No | — | Cluster for notebook execution |

---

## Project Architecture (Summary)

```
User uploads ad image + brand name
        │
        ▼
Creative Extractor (vision AI) → CreativeCard
        │
        ▼
Cohort Selection → top N personas by category affinity
        │
        ▼
Persona Evaluations (vision-native, concurrent)
        │
        ▼
Critic Agent (quality gate: PASS → pipeline, FAIL → quarantine)
        │
        ▼
Medallion Pipeline: Bronze → Silver → Gold (Databricks Delta)
        │
        ▼
Recommendation Agent → SCALE / ITERATE / KILL + edit playbook
```

- **20 personas**, 8 archetypes, 10 Indian cities
- **18 B2C categories** (Quick Commerce, Beauty, EdTech, etc.)
- **Dual quality gates**: schema validation at Silver + Critic Agent behavioral checks
- **MLflow tracking** for every simulation run
- **≈ $0.25 per run**

See `capstone_submission.md` for the full course technology mapping (Weeks 1–5).

---

## License

Educational project — DataExpert Capstone 2026.
