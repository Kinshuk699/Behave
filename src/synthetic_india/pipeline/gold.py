"""
Gold Layer — aggregated, business-ready outputs.

Produces the final tables that feed the recommendation agent
and the dashboard:
- Creative scorecards
- Segment summaries
- Agent recommendations
- Run audit logs
- Memory retrieval analytics

In Databricks, these are Delta tables in the gold schema.
Locally, they are materialized from run outputs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from synthetic_india.config import DATA_DIR

GOLD_DIR = DATA_DIR / "gold"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def materialize_scorecards(run_dir: Path) -> list[dict[str, Any]]:
    """
    Read scorecards from a run and materialize into gold.

    Gold table: gold_creative_scorecards
    """
    gold_out = _ensure_dir(GOLD_DIR / "creative_scorecards")
    scorecards_path = run_dir / "scorecards.json"
    if not scorecards_path.exists():
        return []

    scorecards = json.loads(scorecards_path.read_text())

    for sc in scorecards:
        sc["_materialized_at"] = datetime.utcnow().isoformat()
        out_path = gold_out / f"{sc['run_id']}_{sc['creative_id']}.json"
        out_path.write_text(json.dumps(sc, indent=2, default=str))

    return scorecards


def materialize_recommendations(run_dir: Path) -> dict[str, Any] | None:
    """
    Read recommendation from a run and materialize into gold.

    Gold table: gold_agent_recommendations
    """
    gold_out = _ensure_dir(GOLD_DIR / "agent_recommendations")
    rec_path = run_dir / "recommendation.json"
    if not rec_path.exists():
        return None

    rec = json.loads(rec_path.read_text())
    rec["_materialized_at"] = datetime.utcnow().isoformat()

    out_path = gold_out / f"{rec['run_id']}.json"
    out_path.write_text(json.dumps(rec, indent=2, default=str))
    return rec


def materialize_run_audit(run_dir: Path) -> dict[str, Any] | None:
    """
    Read run metadata and produce an audit log entry.

    Gold table: gold_run_audit_log
    """
    gold_out = _ensure_dir(GOLD_DIR / "run_audit_log")
    meta_path = run_dir / "metadata.json"
    if not meta_path.exists():
        return None

    meta = json.loads(meta_path.read_text())

    audit = {
        "run_id": meta["run_id"],
        "brand": meta["brand"],
        "category": meta["category"],
        "n_creatives": len(meta.get("creative_ids", [])),
        "n_personas": meta.get("cohort_size", 0),
        "total_evaluations": meta.get("total_evaluations", 0),
        "successful_evaluations": meta.get("successful_evaluations", 0),
        "failed_evaluations": meta.get("failed_evaluations", 0),
        "quarantined_records": meta.get("quarantined_records", 0),
        "total_cost_usd": meta.get("total_cost_usd", 0),
        "total_tokens": meta.get("total_tokens", 0),
        "started_at": meta.get("started_at"),
        "completed_at": meta.get("completed_at"),
        "status": meta.get("status"),
        "_materialized_at": datetime.utcnow().isoformat(),
    }

    out_path = gold_out / f"{meta['run_id']}.json"
    out_path.write_text(json.dumps(audit, indent=2, default=str))
    return audit


def materialize_memory_analytics(memory_dir: Path) -> list[dict[str, Any]]:
    """
    Produce memory analytics from all persona memory streams.

    Gold table: gold_memory_analytics
    Tracks per-persona memory growth, reflection counts, and category coverage.
    """
    gold_out = _ensure_dir(GOLD_DIR / "memory_analytics")
    analytics = []

    if not memory_dir.exists():
        return analytics

    for f in memory_dir.glob("*_memory.json"):
        data = json.loads(f.read_text())
        nodes = data.get("nodes", [])

        record = {
            "persona_id": data.get("persona_id"),
            "total_memories": len(nodes),
            "observations": sum(1 for n in nodes if n.get("memory_type") == "observation"),
            "reflections": sum(1 for n in nodes if n.get("memory_type") == "reflection"),
            "preferences": sum(1 for n in nodes if n.get("memory_type") == "preference"),
            "categories_seen": list(set(
                n.get("category") for n in nodes if n.get("category")
            )),
            "brands_seen": list(set(
                n.get("brand") for n in nodes if n.get("brand")
            )),
            "reflection_count": data.get("reflection_count", 0),
            "avg_importance": (
                sum(n.get("importance", 0) for n in nodes) / len(nodes)
                if nodes else 0
            ),
            "last_updated": data.get("updated_at"),
            "_materialized_at": datetime.utcnow().isoformat(),
        }

        analytics.append(record)
        out_path = gold_out / f"{record['persona_id']}.json"
        out_path.write_text(json.dumps(record, indent=2, default=str))

    return analytics


def materialize_all(run_id: str) -> dict[str, Any]:
    """Run the full gold materialization for a completed simulation run."""
    from synthetic_india.config import RUNS_DIR

    run_dir = RUNS_DIR / run_id
    memory_dir = DATA_DIR / "memory"

    results = {
        "scorecards": len(materialize_scorecards(run_dir)),
        "recommendation": materialize_recommendations(run_dir) is not None,
        "audit": materialize_run_audit(run_dir) is not None,
        "memory_analytics": len(materialize_memory_analytics(memory_dir)),
    }

    return results
