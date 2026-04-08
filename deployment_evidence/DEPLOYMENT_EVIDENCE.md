# Deployment Evidence — Behave (Synthetic India)

**Kinshuk Sahni · DataExpert Bootcamp · April 2026**

---

## Live URL

**https://behave-kpe2.onrender.com/**

Dashboard password: `behave2026`

---

## Health Check (Verified April 5, 2026)

```
GET https://behave-kpe2.onrender.com/api/health
→ 200 OK
→ {"status": "ok"}
```

---

## Platform

- **Provider**: Render.com (cloud PaaS)
- **Service type**: Web Service
- **Region**: Singapore (ap-southeast-1)
- **Runtime**: Python 3.12
- **Build**: `pip install -r requirements.txt`
- **Start**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- **Config**: `/dashboard/render.yaml` (committed to repo)

---

## What Is Deployed

The full Behave simulation engine and dashboard:

- **FastAPI backend** — `/api/simulate` (live AI simulation), `/api/preloaded` (Zepto case study)
- **Vanilla JS frontend** — no build step, served as static files
- **20 personas** bundled in `data/personas/`
- **Preloaded run data** bundled in `data/runs/`
- **All agents** — Creative Extractor, Persona Evaluator, Critic Agent, Recommendation Agent

---

## Screenshots

See attached screenshots in this folder:
- `screenshot_1_hero.png` — Landing page with preloaded KILL verdict
- `screenshot_2_full_run.png` — Full simulation result page

---

## GitHub Repository

The application is deployed directly from the connected GitHub repository.
Branch: `main` · Auto-deploy on push: enabled.

---

## Note on Free Tier Spin-Down

The free tier on Render spins down after 15 minutes of inactivity. The first request after inactivity takes ~30 seconds to wake up. This is normal behavior for the free hosting tier and does not affect functionality. For a live demo, simply open the URL and wait for the initial load — all features are fully available once active.
