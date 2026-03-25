# Live Dashboard — Behave Demo Site

**Status:** Built ✅ | Tests GREEN (75/75) ✅ | Local Verified ✅
**Files:** `dashboard/app.py`, `dashboard/static/index.html`, `dashboard/static/styles.css`, `dashboard/static/app.js`
**Hosting:** Render (render.yaml config ready)

## What It Does

Password-gated web app for live capstone demos. Two modes:

1. **Pre-loaded Zepto case study** — loads instantly, shows full pipeline output (scores, personas, segments, verbatims, recommendation, radar chart)
2. **Test Your Own** — upload a creative, configure memory scope and cohort size, run a live simulation via `/api/simulate`

## Architecture

- **Backend:** FastAPI serving static files + 3 API endpoints
  - `GET /api/health` — liveness check
  - `GET /api/preloaded` — returns embedded Zepto run data
  - `POST /api/simulate` — password-gated, runs `run_simulation()` from the engine
- **Frontend:** Vanilla HTML/CSS/JS, no framework, no build step
  - Canvas-based radar chart (no chart library)
  - Dark/moody aesthetic (Instrument Serif + DM Sans)
- **Deployment:** Render free tier, `render.yaml` configures env vars

## Key Decisions

- Password gate (`behave2026`) protects API credits — only `/api/simulate` requires it
- Memory scope is user-choosable (NONE / CATEGORY / BRAND / FULL dropdown)
- Cohort capped at 10 personas for cost control
- Pre-loaded data embedded directly in HTML as `<script type="application/json">` — no extra API call on page load
- XSS protection via `esc()` text escape helper in JS

← [MLflow Tracking](13-mlflow-tracking.md)
