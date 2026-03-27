"""Read personas and memory nodes from Databricks with local fallback.

Tries Databricks SQL via the SDK first.  If the SDK isn't installed, auth
fails, or the query errors out, falls back to the local JSON files so the
simulation always works offline.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from synthetic_india.config import DATA_DIR, PERSONAS_DIR
from synthetic_india.schemas.persona import PersonaProfile
from synthetic_india.schemas.memory import MemoryNode

logger = logging.getLogger(__name__)

# Databricks SQL endpoints
CATALOG = "bootcamp_students"
SILVER = "kinshuk_silver"
CLUSTER_ID = os.getenv("DATABRICKS_CLUSTER_ID", "0208-074755-vt50q0b6")
MEMORY_DIR = DATA_DIR / "memory"


def _get_client():
    """Get a Databricks WorkspaceClient (reuses ingest auth logic)."""
    from databricks.sdk import WorkspaceClient

    profile = os.getenv("DATABRICKS_PROFILE", "Capstone Kinshuk")
    try:
        return WorkspaceClient(profile=profile)
    except Exception:
        return WorkspaceClient()


def _execute_sql(sql: str) -> list[dict]:
    """Execute a SQL statement via Databricks statement execution API.

    Returns a list of row dicts.
    """
    from databricks.sdk.service.sql import StatementState

    client = _get_client()
    response = client.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=os.getenv("DATABRICKS_WAREHOUSE_ID", ""),
        catalog=CATALOG,
        schema=SILVER,
        wait_timeout="30s",
    )

    if response.status and response.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"SQL failed: {response.status.error}")

    if not response.manifest or not response.result:
        return []

    columns = [col.name for col in response.manifest.schema.columns]
    rows = []
    for chunk in (response.result.data_array or []):
        rows.append(dict(zip(columns, chunk)))
    return rows


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

def _read_personas_from_databricks() -> list[PersonaProfile]:
    """Read persona profiles from Databricks silver.personas table."""
    rows = _execute_sql(f"SELECT * FROM {CATALOG}.{SILVER}.personas")
    personas = []
    for row in rows:
        # The persona JSON is stored as a serialized column
        # Try to reconstruct the PersonaProfile from the row
        if "persona_json" in row:
            data = json.loads(row["persona_json"])
        else:
            data = row
        personas.append(PersonaProfile.model_validate(data))
    return personas


def _read_personas_from_local(directory: Optional[Path] = None) -> list[PersonaProfile]:
    """Read persona profiles from local JSON files."""
    persona_dir = directory or PERSONAS_DIR
    personas = []
    for path in sorted(persona_dir.glob("*.json")):
        data = json.loads(path.read_text())
        personas.append(PersonaProfile.model_validate(data))
    return personas


def read_personas(directory: Optional[Path] = None) -> list[PersonaProfile]:
    """Read personas from Databricks, falling back to local files."""
    try:
        personas = _read_personas_from_databricks()
        if personas:
            logger.info("Loaded %d personas from Databricks", len(personas))
            return personas
    except Exception as exc:
        logger.debug("Databricks persona read failed, using local: %s", exc)

    return _read_personas_from_local(directory)


# ---------------------------------------------------------------------------
# Memory nodes
# ---------------------------------------------------------------------------

def _read_memory_nodes_from_databricks(persona_id: str) -> list[MemoryNode]:
    """Read memory nodes for a persona from Databricks silver.memory_nodes."""
    # Parameterize safely — persona_id is an internal ID, not user input
    sql = (
        f"SELECT * FROM {CATALOG}.{SILVER}.memory_nodes "
        f"WHERE persona_id = '{persona_id}' "
        f"ORDER BY created_at"
    )
    rows = _execute_sql(sql)
    nodes = []
    for row in rows:
        nodes.append(MemoryNode.model_validate(row))
    return nodes


def _read_memory_nodes_from_local(
    persona_id: str, directory: Optional[Path] = None
) -> list[MemoryNode]:
    """Read memory nodes from local JSON file."""
    mem_dir = directory or MEMORY_DIR
    path = mem_dir / f"{persona_id}_memory.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    nodes = []
    for node_data in data.get("nodes", []):
        nodes.append(MemoryNode.model_validate(node_data))
    return nodes


def read_memory_nodes(
    persona_id: str, directory: Optional[Path] = None
) -> list[MemoryNode]:
    """Read memory nodes from Databricks, falling back to local files."""
    try:
        nodes = _read_memory_nodes_from_databricks(persona_id)
        if nodes:
            logger.info(
                "Loaded %d memory nodes for %s from Databricks",
                len(nodes), persona_id,
            )
            return nodes
    except Exception as exc:
        logger.debug(
            "Databricks memory read failed for %s, using local: %s",
            persona_id, exc,
        )

    return _read_memory_nodes_from_local(persona_id, directory)
