"""
Databricks Gold Layer — aggregate silver data into analytics-ready rows.

Produces scorecard and audit dicts suitable for Delta table writes.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any


def build_scorecard_row(
    run_id: str,
    creative_id: str,
    eval_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Aggregate evaluation rows for one creative into a scorecard dict.

    Gold table: gold_creative_scorecards
    """
    n = len(eval_rows)
    if n == 0:
        return {}

    actions = Counter(r.get("primary_action", "unknown") for r in eval_rows)
    sentiments = Counter(r.get("sentiment", "unknown") for r in eval_rows)

    avg = lambda key: round(sum(float(r.get(key, 0)) for r in eval_rows) / n, 2)

    return {
        "run_id": run_id,
        "creative_id": creative_id,
        "brand": eval_rows[0].get("brand", ""),
        "category": eval_rows[0].get("category", ""),
        "n_personas_evaluated": n,
        "avg_overall_score": avg("overall_score"),
        "avg_attention": avg("attention_score"),
        "avg_relevance": avg("relevance_score"),
        "avg_trust": avg("trust_score"),
        "avg_desire": avg("desire_score"),
        "avg_clarity": avg("clarity_score"),
        "action_distribution": json.dumps(dict(actions)),
        "sentiment_distribution": json.dumps(dict(sentiments)),
        "_materialized_at": datetime.now(timezone.utc).isoformat(),
    }


def build_audit_row(
    run_id: str,
    brand: str,
    category: str,
    n_creatives: int,
    n_evaluations: int,
    n_passed: int,
    n_quarantined: int,
) -> dict[str, Any]:
    """
    Build a run audit log entry.

    Gold table: gold_run_audit_log
    """
    return {
        "run_id": run_id,
        "brand": brand,
        "category": category,
        "n_creatives": n_creatives,
        "total_evaluations": n_evaluations,
        "successful_evaluations": n_passed,
        "quarantined_records": n_quarantined,
        "_materialized_at": datetime.now(timezone.utc).isoformat(),
    }
