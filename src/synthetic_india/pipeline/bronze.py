"""
Bronze Layer — raw ingestion of all source data.

This module handles landing raw data into the bronze layer:
- Creative uploads (raw ad metadata and content)
- Persona seeds (raw persona JSON records)
- Market context (category benchmarks, price bands, trends)
- Memory stream snapshots (raw memory nodes from persona evaluations)
- Run requests (simulation run metadata)

In Databricks, these become Delta tables in the bronze schema.
Locally, they are persisted as JSON files under data/bronze/.

Key principle: Bronze is append-only and immutable.
No transformations, no cleaning, no deduplication.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from synthetic_india.config import DATA_DIR

BRONZE_DIR = DATA_DIR / "bronze"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _append_record(table_dir: Path, record: dict[str, Any], record_id: str) -> Path:
    """Append a single record to a bronze table (one JSON file per record)."""
    table_dir = _ensure_dir(table_dir)
    record["_ingested_at"] = datetime.utcnow().isoformat()
    path = table_dir / f"{record_id}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    return path


def _append_batch(table_dir: Path, records: list[dict[str, Any]], batch_id: str) -> Path:
    """Append a batch of records to a bronze table."""
    table_dir = _ensure_dir(table_dir)
    for record in records:
        record["_ingested_at"] = datetime.utcnow().isoformat()
        record["_batch_id"] = batch_id
    path = table_dir / f"batch_{batch_id}.json"
    path.write_text(json.dumps(records, indent=2, default=str))
    return path


# ── Bronze Tables ─────────────────────────────────────────────


def ingest_creative_upload(record: dict[str, Any]) -> Path:
    """Land a raw creative upload into bronze_creative_uploads."""
    return _append_record(
        BRONZE_DIR / "creative_uploads",
        record,
        record.get("upload_id", f"upload_{datetime.utcnow().timestamp():.0f}"),
    )


def ingest_persona_seed(record: dict[str, Any]) -> Path:
    """Land a raw persona seed into bronze_persona_seed."""
    return _append_record(
        BRONZE_DIR / "persona_seed",
        record,
        record.get("persona_id", f"persona_{datetime.utcnow().timestamp():.0f}"),
    )


def ingest_market_context(records: list[dict[str, Any]], batch_id: str) -> Path:
    """Land market context records into bronze_market_context."""
    return _append_batch(BRONZE_DIR / "market_context", records, batch_id)


def ingest_memory_snapshot(record: dict[str, Any]) -> Path:
    """
    Land a memory stream snapshot into bronze_memory_stream.

    This is the streaming/incremental data source:
    every simulation run produces new memory nodes that flow into bronze.
    """
    return _append_record(
        BRONZE_DIR / "memory_stream",
        record,
        record.get("node_id", f"mem_{datetime.utcnow().timestamp():.0f}"),
    )


def ingest_run_request(record: dict[str, Any]) -> Path:
    """Land a simulation run request into bronze_run_requests."""
    return _append_record(
        BRONZE_DIR / "run_requests",
        record,
        record.get("run_id", f"run_{datetime.utcnow().timestamp():.0f}"),
    )


def ingest_evaluation(record: dict[str, Any]) -> Path:
    """Land a raw evaluation result into bronze_evaluations."""
    return _append_record(
        BRONZE_DIR / "evaluations",
        record,
        record.get("evaluation_id", f"eval_{datetime.utcnow().timestamp():.0f}"),
    )


# ── Bulk Ingestion ────────────────────────────────────────────


def ingest_all_personas_from_library(persona_dir: Path) -> list[Path]:
    """Load all persona JSON files and land them in bronze."""
    paths = []
    for f in sorted(persona_dir.glob("*.json")):
        record = json.loads(f.read_text())
        paths.append(ingest_persona_seed(record))
    return paths
