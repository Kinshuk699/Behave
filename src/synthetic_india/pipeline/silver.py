"""
Silver Layer — cleaned, validated, and enriched data.

Transforms bronze records into silver tables with:
- Schema validation
- Required field checks
- Value range enforcement
- Deduplication
- Quarantine routing for bad records
- Enrichment (e.g., computing derived fields)

In Databricks, these are Delta tables with DLT expectations.
Locally, they are persisted as JSON files under data/silver/.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from synthetic_india.config import DATA_DIR
from synthetic_india.schemas.creative import CreativeCard
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.memory import MemoryNode
from synthetic_india.schemas.persona import PersonaProfile

SILVER_DIR = DATA_DIR / "silver"
QUARANTINE_DIR = SILVER_DIR / "quarantine"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class QualityResult:
    """Result of a quality check — pass or fail with reasons."""

    def __init__(self, passed: bool, record_id: str, errors: Optional[list[str]] = None):
        self.passed = passed
        self.record_id = record_id
        self.errors = errors or []


# ── Silver: Personas ──────────────────────────────────────────


def validate_persona(raw: dict[str, Any]) -> tuple[Optional[PersonaProfile], QualityResult]:
    """
    Validate and clean a raw persona record.

    Quality checks:
    - Schema compliance (Pydantic validation)
    - Required fields present
    - Score ranges valid (0-1)
    - At least one category affinity
    """
    record_id = raw.get("persona_id", "unknown")
    errors = []

    try:
        persona = PersonaProfile.model_validate(raw)
    except ValidationError as e:
        errors.extend([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    # Additional business rules
    if not persona.backstory or len(persona.backstory) < 20:
        errors.append("backstory too short — personas need rich grounding")

    if not persona.category_affinities:
        errors.append("no category affinities — persona will not match any cohort")

    if errors:
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    return persona, QualityResult(passed=True, record_id=record_id)


# ── Silver: Creative Cards ───────────────────────────────────


def validate_creative_card(raw: dict[str, Any]) -> tuple[Optional[CreativeCard], QualityResult]:
    """
    Validate and clean a creative card.

    Quality checks:
    - Schema compliance
    - At least headline or body_copy present
    - Category in allowed set
    - Extraction confidence above threshold
    """
    record_id = raw.get("creative_id", "unknown")
    errors = []

    try:
        card = CreativeCard.model_validate(raw)
    except ValidationError as e:
        errors.extend([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    # Business rules
    if not card.headline and not card.body_copy:
        errors.append("neither headline nor body_copy extracted — creative has no text content")

    if card.extraction_confidence < 0.3:
        errors.append(f"extraction_confidence too low: {card.extraction_confidence}")

    if card.price_shown and card.price_shown < 0:
        errors.append(f"negative price: {card.price_shown}")

    if card.discount_percentage and (card.discount_percentage < 0 or card.discount_percentage > 100):
        errors.append(f"invalid discount: {card.discount_percentage}%")

    if errors:
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    return card, QualityResult(passed=True, record_id=record_id)


# ── Silver: Evaluations ──────────────────────────────────────


def validate_evaluation(raw: dict[str, Any]) -> tuple[Optional[PersonaEvaluation], QualityResult]:
    """
    Validate an evaluation result.

    Quality checks:
    - Schema compliance
    - Score ranges valid
    - Required text fields non-empty
    - Action is valid enum value
    """
    record_id = raw.get("evaluation_id", "unknown")
    errors = []

    try:
        evaluation = PersonaEvaluation.model_validate(raw)
    except ValidationError as e:
        errors.extend([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    if not evaluation.reasoning or len(evaluation.reasoning) < 10:
        errors.append("reasoning too short — evaluation lacks substance")

    if not evaluation.verbatim_reaction or len(evaluation.verbatim_reaction) < 5:
        errors.append("verbatim_reaction too short")

    if errors:
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    return evaluation, QualityResult(passed=True, record_id=record_id)


# ── Silver: Memory Nodes ─────────────────────────────────────


def validate_memory_node(raw: dict[str, Any]) -> tuple[Optional[MemoryNode], QualityResult]:
    """Validate a memory node."""
    record_id = raw.get("node_id", "unknown")
    errors = []

    try:
        node = MemoryNode.model_validate(raw)
    except ValidationError as e:
        errors.extend([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    if not node.description or len(node.description) < 10:
        errors.append("description too short")

    if errors:
        return None, QualityResult(passed=False, record_id=record_id, errors=errors)

    return node, QualityResult(passed=True, record_id=record_id)


# ── Quarantine ────────────────────────────────────────────────


def quarantine_record(
    raw: dict[str, Any],
    quality_result: QualityResult,
    source_table: str,
) -> Path:
    """Route a failed record to quarantine with error details."""
    qdir = _ensure_dir(QUARANTINE_DIR / source_table)
    record = {
        "record_id": quality_result.record_id,
        "source_table": source_table,
        "errors": quality_result.errors,
        "quarantined_at": datetime.utcnow().isoformat(),
        "raw_data": raw,
    }
    path = qdir / f"{quality_result.record_id}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    return path


# ── Batch Processing ─────────────────────────────────────────


def process_silver_personas(bronze_dir: Path) -> dict[str, Any]:
    """Process all bronze persona records through silver validation."""
    source = bronze_dir / "persona_seed"
    if not source.exists():
        return {"processed": 0, "passed": 0, "quarantined": 0}

    silver_out = _ensure_dir(SILVER_DIR / "personas")
    processed = passed = quarantined = 0

    for f in source.glob("*.json"):
        raw = json.loads(f.read_text())
        if isinstance(raw, list):
            records = raw
        else:
            records = [raw]

        for record in records:
            processed += 1
            persona, result = validate_persona(record)
            if result.passed and persona:
                out_path = silver_out / f"{persona.persona_id}.json"
                out_path.write_text(persona.model_dump_json(indent=2))
                passed += 1
            else:
                quarantine_record(record, result, "persona_seed")
                quarantined += 1

    return {"processed": processed, "passed": passed, "quarantined": quarantined}


def process_silver_evaluations(bronze_dir: Path) -> dict[str, Any]:
    """Process all bronze evaluation records through silver validation."""
    source = bronze_dir / "evaluations"
    if not source.exists():
        return {"processed": 0, "passed": 0, "quarantined": 0}

    silver_out = _ensure_dir(SILVER_DIR / "evaluations")
    processed = passed = quarantined = 0

    for f in source.glob("*.json"):
        raw = json.loads(f.read_text())
        if isinstance(raw, list):
            records = raw
        else:
            records = [raw]

        for record in records:
            processed += 1
            evaluation, result = validate_evaluation(record)
            if result.passed and evaluation:
                out_path = silver_out / f"{evaluation.evaluation_id}.json"
                out_path.write_text(evaluation.model_dump_json(indent=2))
                passed += 1
            else:
                quarantine_record(record, result, "evaluations")
                quarantined += 1

    return {"processed": processed, "passed": passed, "quarantined": quarantined}
