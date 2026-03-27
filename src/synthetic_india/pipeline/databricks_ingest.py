"""Auto-ingest simulation runs to Databricks.

After each simulation run, uploads JSON files to the Databricks workspace
and triggers the ingest notebook to process them through the medallion pipeline.

Gracefully degrades: if the SDK isn't installed or auth fails, the run
still completes locally — Databricks ingest is best-effort.
"""

import logging
import os
import time
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
    "memory_nodes.json",
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


# Poll interval and max wait for synchronous ingest
_POLL_INTERVAL_SECONDS = 10
_MAX_WAIT_SECONDS = 180


def wait_for_job(job_run_id: str, timeout: int = _MAX_WAIT_SECONDS) -> bool:
    """Poll a Databricks job run until it terminates or times out.

    Returns True if the job completed successfully.
    """
    client = _get_client()
    start = time.time()

    while time.time() - start < timeout:
        try:
            run = client.jobs.get_run(int(job_run_id))
            state = run.state.life_cycle_state
            lcs = state.value if hasattr(state, "value") else str(state)

            if lcs in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
                result = run.state.result_state
                rs = result.value if hasattr(result, "value") else str(result)
                if rs == "SUCCESS":
                    logger.info("Databricks job %s completed successfully", job_run_id)
                    return True
                else:
                    logger.warning("Databricks job %s finished with result: %s", job_run_id, rs)
                    return False
        except Exception as exc:
            logger.warning("Error polling job %s: %s", job_run_id, exc)
            return False

        time.sleep(_POLL_INTERVAL_SECONDS)

    logger.warning("Timed out waiting for Databricks job %s after %ds", job_run_id, timeout)
    return False


def auto_ingest(run_id: str, run_dir: Path, wait: bool = False) -> bool:
    """Upload run files and trigger the ingest notebook.

    Best-effort: returns False and logs warnings on any failure.
    Never raises — simulation should not fail because of Databricks issues.

    Args:
        wait: If True, poll the Databricks job until it completes (synchronous).
              If False (default), fire-and-forget.
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
        if job_run_id is None:
            return False

        if wait:
            return wait_for_job(job_run_id)

        return True
    except Exception as exc:
        logger.warning("Databricks auto-ingest failed: %s", exc)
        return False


def backfill_memory_files(
    memory_dir: Path | None = None,
    upload: bool = True,
) -> list[dict]:
    """Read existing local memory JSON files and optionally upload nodes to DBFS.

    Each memory file has structure: {"persona_id": "...", "nodes": [...]}
    Returns the flat list of all node dicts (for testing / manual inspection).
    """
    import json, io

    if memory_dir is None:
        memory_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "memory"

    all_nodes: list[dict] = []
    for mem_file in sorted(memory_dir.glob("*.json")):
        with open(mem_file) as f:
            data = json.load(f)
        nodes = data.get("nodes", [])
        all_nodes.extend(nodes)

    if upload and all_nodes:
        try:
            client = _get_client()
            dbfs_path = f"{DBFS_RUNS_ROOT}/_backfill/memory_nodes_backfill.json"
            payload = json.dumps(all_nodes, indent=2, default=str).encode()
            client.dbfs.upload(dbfs_path, io.BytesIO(payload), overwrite=True)
            logger.info("Backfilled %d memory nodes to dbfs:%s", len(all_nodes), dbfs_path)
        except Exception as exc:
            logger.warning("Failed to upload backfill: %s", exc)

    return all_nodes
