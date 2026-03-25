"""Helpers for building MLflow-ready payloads from simulation run data."""


def build_mlflow_payload(metadata: dict, scorecard: dict) -> dict:
    """Build a dict with 'params' and 'metrics' keys for MLflow logging."""
    quarantined = metadata.get("quarantined_records", 0)
    total = metadata.get("total_evaluations", 1)
    quarantine_rate = quarantined / total if total else 0.0

    return {
        "params": {
            "run_id": metadata["run_id"],
            "brand": metadata["brand"],
            "category": metadata["category"],
            "cohort_size": str(metadata.get("cohort_size", "")),
        },
        "metrics": {
            "avg_overall_score": scorecard["avg_overall_score"],
            "total_cost_usd": metadata.get("total_cost_usd", 0.0),
            "total_tokens": metadata.get("total_tokens", 0),
            "n_personas_evaluated": scorecard["n_personas_evaluated"],
            "quarantine_rate": quarantine_rate,
        },
    }
