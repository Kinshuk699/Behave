"""Behave — Dashboard API.

Serves the static dashboard and exposes /api/simulate for live runs.
"""

import os
import sys
import json
import hashlib
import base64
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure the project root is on the path so we can import synthetic_india
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

app = FastAPI(title="Behave", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared password for the simulation gate
GATE_PASSWORD = os.getenv("BEHAVE_PASSWORD", "behave2026")


# ── Models ────────────────────────────────────────────────────


class SimulateRequest(BaseModel):
    password: str
    brand: str
    image_base64: str
    memory_scope: str = "category"
    cohort_size: int = 5
    persona_ids: list[str] = []


# ── Routes ────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/personas")
async def list_personas():
    """Return all available personas (id, name, city, archetype)."""
    from synthetic_india.engine.simulation import load_personas

    personas = load_personas()
    return [
        {
            "persona_id": p.persona_id,
            "name": p.name,
            "city": p.demographics.city,
            "archetype": p.archetype.value if hasattr(p.archetype, "value") else str(p.archetype),
        }
        for p in personas
    ]


@app.post("/api/simulate")
async def simulate(req: SimulateRequest):
    import hmac

    if not hmac.compare_digest(req.password, GATE_PASSWORD):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        from synthetic_india.engine.simulation import run_simulation
        from synthetic_india.schemas.creative import CreativeCard, CreativeFormat
        from synthetic_india.memory.consumer import MemoryScope
        from synthetic_india.agents.creative_extractor import extract_creative_from_image

        # Save image to temp file for vision API
        tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_file.write(base64.b64decode(req.image_base64))
        tmp_file.close()
        image_path = tmp_file.name

        # LLM extracts category, headline, cta, brand positioning etc. from image
        creative, extraction_resp = await extract_creative_from_image(
            brand=req.brand,
            image_base64=req.image_base64,
        )
        creative.image_path = image_path

        # Map memory scope
        scope_map = {
            "none": MemoryScope.NONE,
            "category": MemoryScope.CATEGORY,
            "brand": MemoryScope.BRAND,
            "full": MemoryScope.FULL,
        }
        memory_scope = scope_map.get(req.memory_scope, MemoryScope.CATEGORY)

        # Build persona list if specific IDs were selected
        selected_personas = None
        if req.persona_ids:
            from synthetic_india.engine.simulation import load_personas as _load
            all_personas = _load()
            selected_personas = [
                p for p in all_personas if p.persona_id in req.persona_ids
            ]

        scorecards, recommendation, meta = await run_simulation(
            creatives=[creative],
            personas=selected_personas,
            cohort_size=req.cohort_size,
            use_memory=memory_scope != MemoryScope.NONE,
            memory_scope=memory_scope,
        )

        # Clean up temp file
        os.unlink(tmp_file.name)

        # Serialize results
        result = {
            "metadata": meta.model_dump(mode="json"),
            "scorecards": [s.model_dump(mode="json") for s in scorecards],
            "recommendation": recommendation.model_dump(mode="json") if recommendation else None,
            "creative": creative.model_dump(mode="json"),
        }

        # Load evaluations from saved run directory
        run_dir = PROJECT_ROOT / "data" / "runs" / meta.run_id
        evals_path = run_dir / "evaluations.json"
        if evals_path.exists():
            with open(evals_path) as f:
                evals = json.load(f)

            # Enrich evaluations with persona display info
            from synthetic_india.engine.simulation import load_personas as _load_all
            persona_map = {p.persona_id: p for p in _load_all()}
            for ev in evals:
                p = persona_map.get(ev.get("persona_id"))
                if p:
                    ev["persona_name"] = p.name
                    ev["persona_city"] = p.demographics.city
                    ev["persona_archetype"] = p.archetype.value if hasattr(p.archetype, "value") else str(p.archetype)

            result["evaluations"] = evals

        return JSONResponse(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Pre-loaded run data endpoint ──────────────────────────────


@app.get("/api/preloaded")
async def preloaded():
    """Return the pre-loaded Zepto run data."""
    run_dir = PROJECT_ROOT / "data" / "runs" / "run_e3d656cc826e"
    result = {}
    for name in ("metadata", "scorecards", "recommendation", "evaluations", "critic_verdicts"):
        fpath = run_dir / f"{name}.json"
        if fpath.exists():
            with open(fpath) as f:
                result[name] = json.load(f)

    # Enrich evaluations with persona display info
    if "evaluations" in result:
        from synthetic_india.engine.simulation import load_personas as _load_all
        persona_map = {p.persona_id: p for p in _load_all()}
        for ev in result["evaluations"]:
            p = persona_map.get(ev.get("persona_id"))
            if p:
                ev["persona_name"] = p.name
                ev["persona_city"] = p.demographics.city
                ev["persona_archetype"] = p.archetype.value if hasattr(p.archetype, "value") else str(p.archetype)

    return JSONResponse(result)


# ── Static files (must be last) ──────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
