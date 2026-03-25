"""Auto-ingest simulation runs to Databricks.

After each simulation run, uploads JSON files to the Databricks workspace
and triggers the ingest notebook to process them through the medallion pipeline.

Gracefully degrades: if the SDK isn't installed or auth fails, the run
still completes locally — Databricks ingest is best-effort.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Workspace paths (must match databricks.yml bundle deployment)
WORKSPACE_USER = "kinshuk.sahni6@gmail.com"
BUNDLE_ROOT = f"/Workspace/Users/{WORKSPACE_USER}/.bundle/Behave/dev/files"
NOTEBOOK_PATH = f"/Workspace/Users/{WORKSPACE_USER}/.bundle/Behave/dev/files/notebooks/04_simulation_ingest"
CLUSTER_ID = os.getenv("DATABRICKS_CLUSTER_ID", "0208-074755-vt50q0b6")

# DBFS path for auto-ingest uploads (notebook reads from here)
DBFS_RUNS_ROOT = "/synthetic_india/runs"

# JSON files produced by _save_run()
RUN_FILES = [
    "metadata.json",
    "evaluations.json",
    "scorecards.json",
    "recommendation.json",
    "critic_verdicts.json",
    "critic_summary.json",
]


def _workspace_run_path(run_id: str) -> str:
    """Construct the workspace path for a given run's data directory."""
    return f"{BUNDLE_ROOT}/data/runs/{run_id}"


def _dbfs_run_path(run_id: str) -> str:
    """Construct the DBFS path for a given run's data directory."""
    return f"{DBFS_RUNS_ROOT}/{run_id}"


def _get_client():
    """Get a Databricks WorkspaceClient. Raises ImportError if SDK missing."""
    from databricks.sdk import WorkspaceClient

    # Try profile first (local dev), fall back to env vars (Render)
    profile = os.getenv("DATABRICKS_PROFILE", "Capstone Kinshuk")
    try:
        return WorkspaceClient(profile=profile)
    except Exception:
        # Fall back to env-var auth (DATABRICKS_HOST + DATABRICKS_TOKEN)
        return WorkspaceClient()


def upload_run_files(run_id: str, run_dir: Path) -> bool:
    """Upload all JSON files from a local run directory to DBFS.

    Returns True if at least one file was uploaded successfully.
    """
    import io

    client = _get_client()
    dbfs_base = _dbfs_run_path(run_id)
    uploaded = 0

    for filename in RUN_FILES:
        local_path = run_dir / filename
        if not local_path.exists():
            continue
        dbfs_path = f"{dbfs_base}/{filename}"
        try:
            data = local_path.read_bytes()
            client.dbfs.upload(dbfs_path, io.BytesIO(data), overwrite=True)
            uploaded += 1
            logger.info("Uploaded %s → dbfs:%s", filename, dbfs_path)
        except Exception as exc:
            logger.warning("Failed to upload %s: %s", filename, exc)

    return uploaded > 0


def trigger_ingest_notebook(run_id: str) -> str | None:
    """Submit a one-time job run of the ingest notebook with the given run_id.

    Returns the run_id of the Databricks job (not the simulation run_id),
    or None if the trigger failed.
    """
    from databricks.sdk.service.jobs import NotebookTask, SubmitTask

    client = _get_client()
    try:
        response = client.jobs.submit(
            run_name=f"auto-ingest-{run_id}",
            tasks=[
                SubmitTask(
                    task_key="ingest",
                    existing_cluster_id=CLUSTER_ID,
                    notebook_task=NotebookTask(
                        notebook_path=NOTEBOOK_PATH,
                        base_parameters={
                            "run_id": run_id,
                            "storage_root": f"/dbfs{DBFS_RUNS_ROOT}",
                        },
                    ),
                )
            ],
        )
        job_run_id = str(response.run_id)
        logger.info("Triggered ingest notebook — Databricks job run: %s", job_run_id)
        return job_run_id
    except Exception as exc:
        logger.warning("Failed to trigger ingest notebook: %s", exc)
        return None


def auto_ingest(run_id: str, run_dir: Path) -> bool:
    """Upload run files and trigger the ingest notebook.

    Best-effort: returns False and logs warnings on any failure.
    Never raises — simulation should not fail because of Databricks issues.
    """
    try:
        _get_client()  # Fail fast if SDK missing or auth broken
    except (ImportError, Exception) as exc:
        logger.warning("Databricks auto-ingest skipped: %s", exc)
        return False

    try:
        uploaded = upload_run_files(run_id, run_dir)
        if not uploaded:
            logger.warning("No files uploaded for %s — skipping notebook trigger", run_id)
            return False

        job_run_id = trigger_ingest_notebook(run_id)
        return job_run_id is not None
    except Exception as exc:
        logger.warning("Databricks auto-ingest failed: %s", exc)
        return False
