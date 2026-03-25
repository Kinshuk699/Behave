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
    category: str
    headline: str = ""
    body_copy: str = ""
    cta: str = ""
    image_base64: str = ""
    memory_scope: str = "category"
    cohort_size: int = 5


# ── Routes ────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/simulate")
async def simulate(req: SimulateRequest):
    import hmac

    if not hmac.compare_digest(req.password, GATE_PASSWORD):
        raise HTTPException(status_code=403, detail="Invalid password")

    try:
        from synthetic_india.engine.simulation import run_simulation
        from synthetic_india.schemas.creative import CreativeCard, CreativeFormat
        from synthetic_india.memory.consumer import MemoryScope

        # Build creative card
        creative = CreativeCard(
            creative_id=f"live_{hashlib.md5(req.brand.encode()).hexdigest()[:8]}",
            brand=req.brand,
            category=req.category,
            format=CreativeFormat.STATIC_IMAGE,
            headline=req.headline or f"{req.brand} ad",
            body_copy=req.body_copy,
            cta=req.cta or "Shop Now",
        )

        # Handle image if provided
        image_path = None
        tmp_file = None
        if req.image_base64:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp_file.write(base64.b64decode(req.image_base64))
            tmp_file.close()
            image_path = tmp_file.name
            creative.image_path = image_path

        # Map memory scope
        scope_map = {
            "none": MemoryScope.NONE,
            "category": MemoryScope.CATEGORY,
            "brand": MemoryScope.BRAND,
            "full": MemoryScope.FULL,
        }
        memory_scope = scope_map.get(req.memory_scope, MemoryScope.CATEGORY)

        scorecards, recommendation, meta = await run_simulation(
            creatives=[creative],
            cohort_size=min(req.cohort_size, 10),  # Cap at 10 for cost control
            use_memory=memory_scope != MemoryScope.NONE,
            memory_scope=memory_scope,
        )

        # Clean up temp file
        if tmp_file:
            os.unlink(tmp_file.name)

        # Serialize results
        result = {
            "metadata": meta.model_dump(mode="json"),
            "scorecards": [s.model_dump(mode="json") for s in scorecards],
            "recommendation": recommendation.model_dump(mode="json") if recommendation else None,
        }

        # Load evaluations from saved run directory
        run_dir = PROJECT_ROOT / "data" / "runs" / meta.run_id
        evals_path = run_dir / "evaluations.json"
        if evals_path.exists():
            with open(evals_path) as f:
                result["evaluations"] = json.load(f)

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
    return JSONResponse(result)


# ── Static files (must be last) ──────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
