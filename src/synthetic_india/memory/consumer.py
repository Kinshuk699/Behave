"""
Memory Consumer — category-scoped consumption strategy.

Selects between full-dump and scored retrieval based on per-category
memory count. Mirrors how streaming consumers handle backfill (read from
offset 0) vs live consumption (scored/filtered reads).

Phase 1-2: Full dump — entire category stream in context
Phase 3+:  Scored retrieval when category memories exceed threshold
"""

from __future__ import annotations

from typing import Optional

from synthetic_india.config import MemoryConfig, get_memory_config
from synthetic_india.memory.retrieval import MemoryRetriever
from synthetic_india.memory.stream import MemoryStream
from synthetic_india.schemas.memory import MemoryNode, MemoryType


class MemoryConsumer:
    """
    Category-scoped memory consumer with auto-strategy selection.

    - consume_all: full dump of category nodes + optional cross-category reflections
    - consume_scored: scored retrieval via MemoryRetriever (existing path)
    - consume: auto-selects based on per-category node count vs threshold
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or get_memory_config()
        self._retriever = MemoryRetriever(config=self.config)

    def consume_all(
        self,
        stream: MemoryStream,
        category: str,
    ) -> list[MemoryNode]:
        """
        Full dump: all category-matching nodes + cross-category reflections.

        Used when per-category memory count is below threshold.
        Eliminates retrieval errors by surfacing everything relevant.
        """
        category_nodes = stream.get_nodes_by_category(category)

        if self.config.include_cross_reflections:
            reflections = stream.get_nodes_by_type(MemoryType.REFLECTION)
            cross_reflections = [
                r for r in reflections
                if r.category and r.category.lower() != category.lower()
            ]
            return category_nodes + cross_reflections

        return category_nodes

    def consume_scored(
        self,
        stream: MemoryStream,
        query: str,
        category: str,
        top_k: int = 10,
        query_embedding: Optional[list[float]] = None,
    ) -> list[MemoryNode]:
        """
        Scored retrieval: delegates to MemoryRetriever for weighted scoring.

        Used when per-category memory count exceeds threshold.
        """
        scored = self._retriever.retrieve(
            nodes=stream.nodes,
            query_text=query,
            query_embedding=query_embedding,
            top_k=top_k,
            category_filter=category,
        )
        return [s.node for s in scored]

    def consume(
        self,
        stream: MemoryStream,
        query: str,
        category: str,
        top_k: int = 10,
        query_embedding: Optional[list[float]] = None,
    ) -> list[MemoryNode]:
        """
        Auto-select strategy based on per-category node count.

        Below threshold → full dump (offset 0, consume everything)
        At or above threshold → scored retrieval (selective consumption)
        """
        category_count = len(stream.get_nodes_by_category(category))

        if category_count < self.config.full_dump_threshold:
            return self.consume_all(stream, category)
        else:
            return self.consume_scored(
                stream, query, category, top_k, query_embedding
            )
