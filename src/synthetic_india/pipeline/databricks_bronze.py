"""
Databricks Bronze Layer — prepare raw data for Delta table ingestion.

This module provides functions that flatten Pydantic models into
plain dicts suitable for Spark DataFrames and Delta table writes.

Bronze is append-only and immutable. No transformations, no cleaning.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from synthetic_india.schemas.creative import CreativeCard
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.persona import PersonaProfile


def _serialize_value(val: Any) -> Any:
    """Convert a value to a Delta-friendly primitive."""
    if isinstance(val, list):
        return json.dumps(val, default=str)
    if isinstance(val, dict):
        return json.dumps(val, default=str)
    if isinstance(val, datetime):
        return val.isoformat()
    if hasattr(val, "value"):  # Enum
        return val.value
    return val


def _flatten_persona(persona: PersonaProfile) -> dict[str, Any]:
    """Flatten a PersonaProfile into a flat dict for Delta storage."""
    raw = persona.model_dump()

    flat: dict[str, Any] = {
        "persona_id": raw["persona_id"],
        "name": raw["name"],
        "archetype": raw["archetype"],
        "tagline": raw["tagline"],
        "backstory": raw["backstory"],
        "current_life_context": raw["current_life_context"],
        "inner_monologue_style": raw["inner_monologue_style"],
    }

    # Flatten demographics
    demo = raw.get("demographics", {})
    for key in ("age", "gender", "city", "city_tier", "income_segment", "education", "occupation", "family_status"):
        flat[key] = demo.get(key)

    # Flatten purchase_psychology
    psych = raw.get("purchase_psychology", {})
    for key in ("price_sensitivity", "brand_loyalty", "impulse_tendency", "social_proof_need",
                "research_depth", "risk_tolerance", "decision_speed", "deal_sensitivity"):
        flat[key] = psych.get(key)

    # Flatten media_behavior
    media = raw.get("media_behavior", {})
    for key in ("platform_primary", "ad_tolerance", "scroll_speed", "video_preference", "influencer_trust"):
        flat[key] = media.get(key)
    flat["content_language_preference"] = media.get("content_language_preference")

    # Serialize complex nested fields as JSON strings
    flat["category_affinities"] = json.dumps(raw.get("category_affinities", []), default=str)
    flat["emotional_profile"] = json.dumps(raw.get("emotional_profile", {}), default=str)

    return flat


def prepare_personas_for_bronze(personas: list[PersonaProfile]) -> list[dict[str, Any]]:
    """Flatten PersonaProfiles into Delta-ready dicts with ingestion timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for p in personas:
        row = _flatten_persona(p)
        row["_ingested_at"] = now
        rows.append(row)
    return rows


def prepare_creatives_for_bronze(creatives: list[CreativeCard]) -> list[dict[str, Any]]:
    """Flatten CreativeCards into Delta-ready dicts."""
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for c in creatives:
        raw = c.model_dump()
        row: dict[str, Any] = {}
        for key, val in raw.items():
            row[key] = _serialize_value(val)
        row["_ingested_at"] = now
        rows.append(row)
    return rows


def prepare_evaluations_for_bronze(evaluations: list[PersonaEvaluation]) -> list[dict[str, Any]]:
    """Flatten PersonaEvaluations into Delta-ready dicts."""
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for e in evaluations:
        raw = e.model_dump()
        row: dict[str, Any] = {}
        for key, val in raw.items():
            row[key] = _serialize_value(val)
        row["_ingested_at"] = now
        rows.append(row)
    return rows
