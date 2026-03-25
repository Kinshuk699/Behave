"""
Databricks Silver Layer — validate bronze rows for Delta table writes.

Applies the same quality checks as the existing silver.py validators
but operates on flat dicts (bronze rows) instead of Pydantic models.

Returns (passed_rows, quarantined_rows) tuples.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def validate_persona_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validate bronze persona rows.

    Checks:
    - persona_id present
    - backstory present and >= 20 chars
    - archetype present
    - category_affinities present (non-empty JSON array)

    Returns (passed, quarantined).
    """
    passed = []
    quarantined = []
    now = datetime.now(timezone.utc).isoformat()

    for row in rows:
        errors = []

        if not row.get("persona_id"):
            errors.append("missing persona_id")

        backstory = row.get("backstory", "")
        if not backstory or len(str(backstory)) < 20:
            errors.append("backstory too short — personas need rich grounding")

        if not row.get("archetype"):
            errors.append("missing archetype")

        affinities = row.get("category_affinities", "[]")
        if affinities in ("[]", "", None):
            errors.append("no category affinities — persona will not match any cohort")

        if errors:
            quarantined.append({
                "record_id": row.get("persona_id", "unknown"),
                "source_table": "persona_seed",
                "errors": "; ".join(errors),
                "_quarantined_at": now,
            })
        else:
            row_copy = dict(row)
            row_copy["_validated_at"] = now
            passed.append(row_copy)

    return passed, quarantined


def validate_creative_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validate bronze creative rows.

    Checks:
    - creative_id present
    - headline or body_copy present
    - extraction_confidence >= 0.3

    Returns (passed, quarantined).
    """
    passed = []
    quarantined = []
    now = datetime.now(timezone.utc).isoformat()

    for row in rows:
        errors = []

        if not row.get("creative_id"):
            errors.append("missing creative_id")

        if not row.get("headline") and not row.get("body_copy"):
            errors.append("neither headline nor body_copy — creative has no text content")

        conf = row.get("extraction_confidence", 0)
        if conf is not None and float(conf) < 0.3:
            errors.append(f"extraction_confidence too low: {conf}")

        if errors:
            quarantined.append({
                "record_id": row.get("creative_id", "unknown"),
                "source_table": "creative_uploads",
                "errors": "; ".join(errors),
                "_quarantined_at": now,
            })
        else:
            row_copy = dict(row)
            row_copy["_validated_at"] = now
            passed.append(row_copy)

    return passed, quarantined


def validate_evaluation_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validate bronze evaluation rows.

    Checks:
    - evaluation_id present
    - reasoning >= 10 chars
    - verbatim_reaction >= 5 chars

    Returns (passed, quarantined).
    """
    passed = []
    quarantined = []
    now = datetime.now(timezone.utc).isoformat()

    for row in rows:
        errors = []

        if not row.get("evaluation_id"):
            errors.append("missing evaluation_id")

        reasoning = row.get("reasoning", "")
        if not reasoning or len(str(reasoning)) < 10:
            errors.append("reasoning too short — evaluation lacks substance")

        verbatim = row.get("verbatim_reaction", "")
        if not verbatim or len(str(verbatim)) < 5:
            errors.append("verbatim_reaction too short")

        if errors:
            quarantined.append({
                "record_id": row.get("evaluation_id", "unknown"),
                "source_table": "evaluations",
                "errors": "; ".join(errors),
                "_quarantined_at": now,
            })
        else:
            row_copy = dict(row)
            row_copy["_validated_at"] = now
            passed.append(row_copy)

    return passed, quarantined
