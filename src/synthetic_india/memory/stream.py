"""
Memory Stream — append-only store of persona experiences.

Directly inspired by the AssociativeMemory in the Generative Agents repo.
Each persona has its own MemoryStream that accumulates observations
(evaluations) and reflections (synthesized insights) over time.

This creates the streaming/incremental data dimension:
- Every simulation run produces new memory nodes (bronze layer)
- Memory nodes are cleaned and indexed (silver layer)
- Retrieval scores and reflection outputs land in gold
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from synthetic_india.config import DATA_DIR
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.memory import MemoryNode, MemoryStreamState, MemoryType


MEMORY_DIR = DATA_DIR / "memory"


class MemoryStream:
    """
    Append-only memory stream for a single persona.

    Mirrors Park et al.'s AssociativeMemory:
    - stores observations, reflections, preferences, and category beliefs
    - tracks cumulative importance for reflection triggering
    - persists to JSON for durability (Delta table in Databricks)
    """

    def __init__(self, persona_id: str, reflection_threshold: float = 50.0):
        self.persona_id = persona_id
        self.nodes: list[MemoryNode] = []
        self.reflection_threshold = reflection_threshold
        self._importance_since_reflection: float = 0.0
        self._reflection_count: int = 0
        self._last_reflection_at: Optional[datetime] = None
        self._next_sequence_number: int = 0

    @property
    def size(self) -> int:
        return len(self.nodes)

    @property
    def should_reflect(self) -> bool:
        """Check if accumulated importance has crossed the reflection threshold."""
        return self._importance_since_reflection >= self.reflection_threshold

    @property
    def total_importance(self) -> float:
        return sum(n.importance for n in self.nodes)

    def add_node(self, node: MemoryNode) -> None:
        """Add a memory node to the stream, assigning a monotonic sequence number."""
        node.sequence_number = self._next_sequence_number
        self._next_sequence_number += 1
        self.nodes.append(node)
        self._importance_since_reflection += node.importance

    def add_evaluation_memory(self, evaluation: PersonaEvaluation) -> MemoryNode:
        """
        Convert a persona evaluation into a memory node and store it.

        This is the bridge between the evaluation pipeline and the memory system.
        Every time a persona evaluates a creative, it becomes a retrievable memory.
        """
        description = (
            f"I saw a {evaluation.brand} {evaluation.category} ad. "
            f"My first impression: {evaluation.first_impression}. "
            f"I would {evaluation.primary_action.replace('_', ' ')}. "
            f"{evaluation.reasoning}"
        )

        node = MemoryNode(
            node_id=f"mem_{uuid.uuid4().hex[:12]}",
            persona_id=self.persona_id,
            memory_type=MemoryType.OBSERVATION,
            description=description,
            subject=self.persona_id,
            predicate=f"evaluated_{evaluation.primary_action}",
            object=f"{evaluation.brand} {evaluation.category} creative ({evaluation.creative_id})",
            importance=evaluation.importance_score,
            embedding_key=description,
            source_evaluation_id=evaluation.evaluation_id,
            source_run_id=evaluation.run_id,
            creative_id=evaluation.creative_id,
            brand=evaluation.brand,
            category=evaluation.category,
            key_themes=evaluation.key_themes,
        )

        self.add_node(node)
        return node

    def add_preference_memory(
        self,
        brand: str,
        category: str,
        description: str,
        importance: float,
        source_evaluation_id: str,
    ) -> MemoryNode:
        """
        Create a PREFERENCE memory from a strong positive evaluation.

        Called when overall_score > 70 — the persona liked this enough
        to form an enduring preference that influences future evaluations.
        """
        node = MemoryNode(
            node_id=f"pref_{uuid.uuid4().hex[:12]}",
            persona_id=self.persona_id,
            memory_type=MemoryType.PREFERENCE,
            description=description,
            subject=self.persona_id,
            predicate="prefers",
            object=f"{brand} in {category}",
            importance=importance,
            embedding_key=description,
            source_evaluation_id=source_evaluation_id,
            brand=brand,
            category=category,
        )
        self.add_node(node)
        return node

    def add_category_belief_memory(
        self,
        category: str,
        description: str,
        importance: float,
        source_evaluation_id: str,
        brand: Optional[str] = None,
    ) -> MemoryNode:
        """
        Create a CATEGORY_BELIEF memory from a strong negative evaluation.

        Called when overall_score < 30 — the persona disliked this enough
        to form a lasting skepticism or belief about the category/brand.
        """
        node = MemoryNode(
            node_id=f"belief_{uuid.uuid4().hex[:12]}",
            persona_id=self.persona_id,
            memory_type=MemoryType.CATEGORY_BELIEF,
            description=description,
            subject=self.persona_id,
            predicate="believes",
            object=f"{category} category",
            importance=importance,
            embedding_key=description,
            source_evaluation_id=source_evaluation_id,
            brand=brand,
            category=category,
        )
        self.add_node(node)
        return node

    def add_reflection(
        self,
        description: str,
        importance: float,
        evidence_node_ids: list[str],
        category: Optional[str] = None,
    ) -> MemoryNode:
        """
        Add a reflection — a higher-order insight synthesized from observations.

        Directly implements the paper's reflection mechanism:
        "What high-level insights can you infer from the above statements?"

        Examples:
        - "I tend to distrust skincare brands that rely on celebrity endorsements
           without clinical backing."
        - "Brands with transparent pricing consistently earn my attention."
        """
        node = MemoryNode(
            node_id=f"ref_{uuid.uuid4().hex[:12]}",
            persona_id=self.persona_id,
            memory_type=MemoryType.REFLECTION,
            description=description,
            subject=self.persona_id,
            predicate="reflected",
            object=description[:80],
            importance=importance,
            embedding_key=description,
            evidence_node_ids=evidence_node_ids,
            category=category,
        )

        self.add_node(node)
        self._importance_since_reflection = 0.0
        self._reflection_count += 1
        self._last_reflection_at = datetime.utcnow()
        return node

    def get_nodes_by_type(self, memory_type: MemoryType) -> list[MemoryNode]:
        return [n for n in self.nodes if n.memory_type == memory_type]

    def get_nodes_by_category(self, category: str) -> list[MemoryNode]:
        return [n for n in self.nodes if n.category and n.category.lower() == category.lower()]

    def get_nodes_by_brand(self, brand: str) -> list[MemoryNode]:
        return [n for n in self.nodes if n.brand and n.brand.lower() == brand.lower()]

    def get_recent_nodes(self, n: int = 10) -> list[MemoryNode]:
        return sorted(self.nodes, key=lambda x: x.created_at, reverse=True)[:n]

    # ── Persistence ──────────────────────────────────────────

    def to_state(self) -> MemoryStreamState:
        return MemoryStreamState(
            persona_id=self.persona_id,
            nodes=self.nodes,
            total_importance_since_reflection=self._importance_since_reflection,
            reflection_count=self._reflection_count,
            last_reflection_at=self._last_reflection_at,
            updated_at=datetime.utcnow(),
        )

    @classmethod
    def from_state(cls, state: MemoryStreamState) -> MemoryStream:
        stream = cls(persona_id=state.persona_id)
        stream.nodes = state.nodes
        stream._importance_since_reflection = state.total_importance_since_reflection
        stream._reflection_count = state.reflection_count
        stream._last_reflection_at = state.last_reflection_at
        # Restore sequence counter from persisted nodes
        if stream.nodes:
            max_seq = max(
                (n.sequence_number for n in stream.nodes if n.sequence_number is not None),
                default=-1,
            )
            stream._next_sequence_number = max_seq + 1
        return stream

    def save(self, directory: Optional[Path] = None) -> Path:
        """Persist memory stream to JSON file."""
        save_dir = directory or MEMORY_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        path = save_dir / f"{self.persona_id}_memory.json"
        state = self.to_state()
        path.write_text(state.model_dump_json(indent=2))
        return path

    @classmethod
    def load(cls, persona_id: str, directory: Optional[Path] = None) -> MemoryStream:
        """Load a persisted memory stream — tries Databricks, falls back to local."""
        # Try Databricks first (gracefully degrades)
        try:
            from synthetic_india.pipeline.databricks_reader import read_memory_nodes
            db_nodes = read_memory_nodes(persona_id)
            if db_nodes:
                stream = cls(persona_id=persona_id)
                stream.nodes = db_nodes
                if stream.nodes:
                    stream._importance_since_reflection = sum(
                        n.importance for n in stream.nodes
                    )
                    max_seq = max(
                        (n.sequence_number for n in stream.nodes if n.sequence_number is not None),
                        default=-1,
                    )
                    stream._next_sequence_number = max_seq + 1
                return stream
        except Exception:
            pass

        # Fall back to local JSON
        load_dir = directory or MEMORY_DIR
        path = load_dir / f"{persona_id}_memory.json"
        if not path.exists():
            return cls(persona_id=persona_id)
        state = MemoryStreamState.model_validate_json(path.read_text())
        return cls.from_state(state)
