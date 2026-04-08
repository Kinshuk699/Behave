"""
Long-Horizon Memory Retrieval — the core Generative Agents contribution
adapted for consumer behavior simulation.

Retrieves relevant past memories using a weighted combination of:
  - Recency:    exponential decay based on time since memory was created
  - Relevance:  cosine similarity between query embedding and memory embedding
  - Importance: LLM-scored poignancy of the memory

This is what makes personas consistent and evolving across simulation runs.
A persona who distrusted a skincare brand's claims last month will carry
that skepticism into future evaluations — not because we hard-coded it,
but because retrieval surfaces the relevant memory at the right time.

Paper reference: Park et al., Section 5.2 "Retrieval"
  score = α * recency + β * relevance + γ * importance
  recency = decay^(hours_since_creation)
  relevance = cosine_similarity(query_emb, memory_emb)
  importance = poignancy / 10 (normalized to 0-1)
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import numpy as np

from synthetic_india.config import MemoryConfig, get_memory_config
from synthetic_india.schemas.memory import MemoryNode, RetrievalScore


class MemoryRetriever:
    """
    Scores and retrieves memories from a persona's stream
    using the recency + relevance + importance formula.
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or get_memory_config()

    def retrieve(
        self,
        nodes: list[MemoryNode],
        query_embedding: Optional[list[float]] = None,
        query_text: Optional[str] = None,
        now: Optional[datetime] = None,
        top_k: int = 10,
        category_filter: Optional[str] = None,
        brand_filter: Optional[str] = None,
    ) -> list[RetrievalScore]:
        """
        Score all nodes and return the top-k most relevant memories.

        This is the paper's retrieval function:
          composite = α * recency + β * relevance + γ * importance

        Args:
            nodes: All memory nodes to score
            query_embedding: Dense vector for relevance scoring
            query_text: Fallback text for keyword matching if no embedding
            now: Current time for recency calculation
            top_k: Number of results to return
            category_filter: Optional filter to only retrieve memories from this category
            brand_filter: Optional filter to only retrieve memories about this brand
        """
        if not nodes:
            return []

        now = now or datetime.utcnow()

        # Optional pre-filtering
        filtered = nodes
        if category_filter:
            filtered = [
                n for n in filtered
                if n.category and n.category.lower() == category_filter.lower()
            ]
        if brand_filter:
            filtered = [
                n for n in filtered
                if n.brand and n.brand.lower() == brand_filter.lower()
            ]

        if not filtered:
            return []

        scored: list[RetrievalScore] = []
        for node in filtered:
            recency = self._score_recency(node, now)
            relevance = self._score_relevance(node, query_embedding, query_text)
            importance = self._score_importance(node)
            arousal = self._score_arousal(node)
            retrieval_freq = self._score_retrieval_frequency(node)

            # Updated formula (Manufacturing Nostalgia, §7.2):
            # score = α·recency + β·relevance + γ·importance + δ·emotional_arousal + ε·log(1 + retrieval_count)
            # δ=1.5 is higher than other weights so formative high-arousal memories surface even when old
            composite = (
                self.config.recency_weight * recency
                + self.config.relevance_weight * relevance
                + self.config.importance_weight * importance
                + self.config.arousal_weight * arousal
                + self.config.retrieval_count_weight * retrieval_freq
            )

            scored.append(
                RetrievalScore(
                    node=node,
                    recency_score=recency,
                    relevance_score=relevance,
                    importance_score=importance,
                    arousal_score=arousal,
                    composite_score=composite,
                )
            )

        scored.sort(key=lambda s: s.composite_score, reverse=True)

        # Memory strengthening on retrieval (Manufacturing Nostalgia, §7.3 + ACT-R / Hou et al.):
        # Memories that get recalled become stronger — mirrors real human memory consolidation.
        # access_count += 1 (existing), plus tiny boosts to arousal and importance.
        for s in scored[:top_k]:
            s.node.last_accessed_at = now
            s.node.access_count += 1
            # Small arousal boost — accumulates over many retrievals, capped at 1.0
            s.node.emotional_arousal = min(1.0, s.node.emotional_arousal + 0.02)
            # Small importance boost — capped at 10.0
            s.node.importance = min(10.0, s.node.importance + 0.1)

        return scored[:top_k]

    def _score_recency(self, node: MemoryNode, now: datetime) -> float:
        """
        Exponential decay based on hours since creation.
        Paper: recency = decay_factor ^ hours_elapsed
        More recent memories score higher.
        """
        hours_elapsed = (now - node.created_at).total_seconds() / 3600.0
        return self.config.recency_decay ** hours_elapsed

    def _score_relevance(
        self,
        node: MemoryNode,
        query_embedding: Optional[list[float]],
        query_text: Optional[str],
    ) -> float:
        """
        Cosine similarity between query and memory embeddings.
        Falls back to keyword overlap if embeddings are not available.
        """
        # Dense vector similarity
        if query_embedding and node.embedding:
            return self._cosine_similarity(query_embedding, node.embedding)

        # Keyword fallback — not as precise, but works without API calls
        if query_text and node.embedding_key:
            return self._keyword_similarity(query_text, node.embedding_key, node.key_themes)

        return 0.0

    def _score_importance(self, node: MemoryNode) -> float:
        """Normalize importance from 0-10 scale to 0-1."""
        return node.importance / 10.0

    def _score_arousal(self, node: MemoryNode) -> float:
        """
        Return emotional_arousal directly (already 0-1).
        Higher weight (δ=1.5) means high-arousal formative memories surface even
        when they are old and only loosely relevant — exactly how nostalgia works.
        LUFY (Sumida et al., 2024): emotionally arousing memories retrieved preferentially.
        """
        return node.emotional_arousal

    def _score_retrieval_frequency(self, node: MemoryNode) -> float:
        """
        Log-scale retrieval count: ε·log(1 + access_count).
        Diminishing returns: retrieved 10 times gets a boost, not 10x.
        ACT-R / Hou et al. (CHI EA 2024): frequently recalled memories strengthen over time.
        The log is already applied here so the weight in the formula is a linear multiplier.
        """
        return math.log(1 + node.access_count)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two vectors."""
        a_arr = np.array(a, dtype=np.float64)
        b_arr = np.array(b, dtype=np.float64)
        dot = np.dot(a_arr, b_arr)
        norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    @staticmethod
    def _keyword_similarity(
        query: str,
        memory_text: str,
        memory_themes: list[str],
    ) -> float:
        """
        Simple keyword overlap score as a fallback when embeddings
        are not available. Returns 0-1.
        """
        query_tokens = set(query.lower().split())
        memory_tokens = set(memory_text.lower().split())
        theme_tokens = {t.lower() for t in memory_themes}

        if not query_tokens:
            return 0.0

        # Overlap in description text
        text_overlap = len(query_tokens & memory_tokens) / len(query_tokens)

        # Bonus for theme matches
        theme_overlap = len(query_tokens & theme_tokens) / max(len(query_tokens), 1)

        return min(1.0, text_overlap * 0.7 + theme_overlap * 0.3)


class ReflectionEngine:
    """
    Triggers and generates reflections when cumulative importance
    crosses the threshold — directly from the paper's Section 5.3.

    "The agent generates reflections periodically... when the sum of
    importance scores of the latest events exceeds a threshold."
    """

    def generate_reflection_prompt(
        self,
        focal_nodes: list[MemoryNode],
        persona_name: str,
    ) -> str:
        """
        Build the prompt for LLM-based reflection.
        The LLM will synthesize higher-order insights from recent observations.
        """
        statements = []
        for i, node in enumerate(focal_nodes, 1):
            statements.append(f"{i}. {node.description}")

        statements_block = "\n".join(statements)

        return f"""You are {persona_name}, reflecting on your recent experiences evaluating marketing creatives and products.

Here are your recent observations and experiences:

{statements_block}

Based on these experiences, generate 2-3 high-level insights about your preferences, beliefs, or patterns. These should be things you have learned about yourself as a consumer.

Each insight should:
- Be a genuine synthesis, not just a restatement of one observation
- Reflect your personality and decision-making style
- Be useful for guiding future purchase decisions

Format each insight as a single clear sentence starting with "I" (e.g., "I tend to...", "I have noticed that...", "I am drawn to...").

Return ONLY the insights, one per line, no numbering or bullets."""

    def select_focal_nodes(
        self,
        nodes: list[MemoryNode],
        n: int = 15,
    ) -> list[MemoryNode]:
        """
        Select the most important recent nodes as focal points for reflection.
        The paper uses importance-weighted recent retrieval.
        """
        recent = sorted(nodes, key=lambda n: n.created_at, reverse=True)
        # Weight by importance — higher importance = more likely to be selected
        recent_important = sorted(
            recent[:n * 2],
            key=lambda n: n.importance,
            reverse=True,
        )
        return recent_important[:n]
