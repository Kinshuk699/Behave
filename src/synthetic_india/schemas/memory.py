"""
Memory stream models — long-horizon retrieval system inspired by
Park et al. (Generative Agents, UIST 2023).

Each persona accumulates memories from evaluating creatives.
Future evaluations retrieve relevant past memories using a weighted
combination of recency, relevance, and importance — exactly the
paper's retrieval architecture adapted for consumer behavior.

This is what makes personas consistent and evolving across runs,
and creates a natural streaming/incremental data pipeline story.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
    """Types of memory entries in the stream."""
    OBSERVATION = "observation"      # Raw evaluation experience
    REFLECTION = "reflection"        # Higher-order inference synthesized from observations
    PREFERENCE = "preference"        # Learned preference or brand opinion
    CATEGORY_BELIEF = "category_belief"  # General belief about a product category


class MemoryNode(BaseModel):
    """
    A single entry in a persona's memory stream.
    Maps to ConceptNode in the Generative Agents repo.
    """

    node_id: str = Field(..., description="Unique memory identifier")
    persona_id: str
    memory_type: MemoryType
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Content
    description: str = Field(
        ..., description="Natural language description of the memory"
    )
    # Subject-Predicate-Object triple for structured retrieval
    subject: str = Field(..., description="Who/what: persona name, brand, category")
    predicate: str = Field(..., description="Action/relation: evaluated, preferred, distrusted")
    object: str = Field(..., description="Target: brand name, product, creative aspect")

    # Retrieval scoring inputs
    importance: float = Field(
        ..., ge=0, le=10,
        description="Poignancy score — how memorable/impactful this is (LLM-scored)"
    )
    embedding_key: Optional[str] = Field(
        None, description="Text used to generate the embedding vector"
    )
    embedding: Optional[list[float]] = Field(
        None, description="Dense vector for relevance scoring"
    )

    # Context links
    source_evaluation_id: Optional[str] = None
    source_run_id: Optional[str] = None
    creative_id: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    key_themes: list[str] = Field(default_factory=list)

    # For reflections: which memories were synthesized
    evidence_node_ids: list[str] = Field(
        default_factory=list,
        description="IDs of memories that contributed to this reflection"
    )

    # Access tracking
    last_accessed_at: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0

    # Stream offset (assigned by MemoryStream.add_node)
    sequence_number: Optional[int] = Field(
        None, description="Monotonic offset in the stream, assigned on insertion"
    )

    model_config = ConfigDict(use_enum_values=True)


class RetrievalScore(BaseModel):
    """Scored memory during retrieval — wraps a node with its composite score."""

    node: MemoryNode
    recency_score: float = 0.0
    relevance_score: float = 0.0
    importance_score: float = 0.0
    composite_score: float = 0.0


class MemoryStreamState(BaseModel):
    """Snapshot of a persona's full memory state — used for persistence."""

    persona_id: str
    nodes: list[MemoryNode] = Field(default_factory=list)
    total_importance_since_reflection: float = 0.0
    reflection_count: int = 0
    last_reflection_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
