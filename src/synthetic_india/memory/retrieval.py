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
        query_tags: Optional[dict] = None,
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
            relevance = self._score_relevance(node, query_embedding, query_text, query_tags)
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
        query_tags: Optional[dict] = None,
    ) -> float:
        """
        Relevance scoring with three tiers (most-preferred first):
          1. Structured multi-signal score from query_tags (Phase 1, 2026-04-21).
             Categorical + theme + era/sensory match. Resilient to lexical drift
             (Nirma memory ↔ Surf Excel ad scores high without sharing tokens).
          2. Cosine similarity if both query and memory embeddings exist.
          3. Naive whitespace token overlap (legacy fallback).
        """
        # Tier 1: structured tags — the only signal Opus #2 considered acceptable.
        if query_tags:
            return self._structured_relevance(node, query_tags)

        # Tier 2: dense vector similarity
        if query_embedding and node.embedding:
            return self._cosine_similarity(query_embedding, node.embedding)

        # Tier 3: keyword fallback — not precise; kept for back-compat.
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

    # ── Structured relevance (Phase 1, 2026-04-21) ────────────────────
    #
    # Replaces the naive whitespace-token overlap as the primary relevance
    # signal. Token cosine remains a 10% tiebreaker. Cite: Anshuj v3 Part 4
    # ("Multi-Signal Relevance Formula"); Opus pressure-test Issue #2
    # ("Relevance Score is doing all the heavy lifting and you haven't
    # specified how it works").
    #
    # Score = 0.40·category + 0.30·themes + 0.20·era_or_sensory + 0.10·token
    #
    # Each component returns 0-1; final score is in [0, 1].

    # Sibling categories live under the same parent. Exact match = 1.0,
    # sibling = 0.5, otherwise 0. Hand-curated for Indian consumer ad
    # categories common in our persona library; expand as needed.
    _CATEGORY_TREE: dict[str, list[str]] = {
        "personal_care": ["soap", "shampoo", "skincare", "deodorant", "toothpaste"],
        "home_care": ["detergent", "dishwash", "floor_cleaner", "air_freshener"],
        "food_packaged": ["biscuit", "snacks", "noodles", "cereal", "sweets"],
        "beverages": ["tea", "coffee", "soft_drink", "juice"],
        "kitchen_staples": ["salt", "spices", "atta", "oil", "ghee"],
        "apparel": ["apparel", "footwear", "accessories"],
        "tech_consumer": ["smartphone", "laptop", "headphones", "smartwatch"],
        "fintech": ["fintech", "banking", "insurance", "mutual_fund"],
        "automotive": ["car", "two_wheeler", "luxury_car", "ev"],
        "food_service": ["restaurant", "food_delivery", "quick_commerce"],
        "media": ["music", "music_streaming", "video_streaming", "ott"],
    }

    @classmethod
    def _category_match(cls, mem_category: Optional[str], crt_category: Optional[str]) -> float:
        """1.0 exact, 0.5 sibling under same parent, 0.0 otherwise."""
        if not mem_category or not crt_category:
            return 0.0
        m = mem_category.lower()
        c = crt_category.lower()
        if m == c:
            return 1.0
        for siblings in cls._CATEGORY_TREE.values():
            if m in siblings and c in siblings:
                return 0.5
        return 0.0

    @staticmethod
    def _set_overlap(a: list[str], b: list[str]) -> float:
        """Symmetric Jaccard-like overlap. Returns 0 if either set is empty."""
        if not a or not b:
            return 0.0
        sa = {s.lower().strip() for s in a if s}
        sb = {s.lower().strip() for s in b if s}
        if not sa or not sb:
            return 0.0
        intersection = len(sa & sb)
        if intersection == 0:
            return 0.0
        # Recall over the smaller set — captures "this memory's anchors are
        # well-covered by this ad's signifiers" without requiring the ad to
        # match every single anchor.
        return intersection / min(len(sa), len(sb))

    def _structured_relevance(
        self,
        node: MemoryNode,
        creative_tags: dict,
    ) -> float:
        """
        Multi-signal relevance score in [0, 1].

        Args:
            node: A MemoryNode with category/brand/key_themes/memory_era/sensory_anchors.
            creative_tags: A dict shaped like
                {
                    "category": str,
                    "brand": Optional[str],
                    "themes": list[str],
                    "era_signifiers": list[str],
                    "sensory": list[str],
                }
                Built from CreativeCard fields by build_creative_tags().

        Weights (rationale in Anshuj v3 Part 4):
            0.40 category — strongest deterministic signal; exact = 1.0, sibling = 0.5
            0.30 themes  — emotional/positioning overlap (Bower mood-congruence)
            0.20 era + sensory — reminiscence-bump cue match (Chu & Downes)
            0.10 token cosine — last-resort tiebreaker on description text
        """
        cat_score = self._category_match(node.category, creative_tags.get("category"))
        theme_score = self._set_overlap(
            node.key_themes,
            creative_tags.get("themes") or [],
        )
        era_score = self._set_overlap(
            (node.sensory_anchors or []) + ([node.memory_era] if node.memory_era else []),
            (creative_tags.get("era_signifiers") or []) + (creative_tags.get("sensory") or []),
        )

        # Token similarity tiebreaker — only against description, not the full
        # query. Kept low-weight precisely because Opus #2 calls this signal a
        # black box.
        token_score = 0.0
        if node.embedding_key:
            tag_blob = " ".join(
                [creative_tags.get("category") or ""]
                + (creative_tags.get("themes") or [])
                + (creative_tags.get("era_signifiers") or [])
                + (creative_tags.get("sensory") or [])
            ).strip()
            if tag_blob:
                token_score = self._keyword_similarity(tag_blob, node.embedding_key, node.key_themes)

        return min(
            1.0,
            0.40 * cat_score
            + 0.30 * theme_score
            + 0.20 * era_score
            + 0.10 * token_score,
        )


def build_creative_tags(creative) -> dict:
    """
    Build the structured-relevance tag dict from a CreativeCard.

    Pulled from existing CreativeCard fields — no new schema fields required.
    Robust to missing values (returns empty lists, not None).

    Mapping rationale:
      themes         <- emotional_hooks + [marketing_tone] + [brand_positioning]
      era_signifiers <- cultural_references + [festival_context] + [brand_era]
      sensory        <- [visual_style] + [color_dominant]
                        (CreativeCard does not yet carry sensory tags directly;
                         visual style is the closest proxy until Phase 2 enriches
                         the creative analyzer to extract sensory anchors.)
    """
    if creative is None:
        return {"category": None, "brand": None, "themes": [], "era_signifiers": [], "sensory": []}

    themes: list[str] = []
    themes.extend(getattr(creative, "emotional_hooks", []) or [])
    if getattr(creative, "marketing_tone", None):
        themes.append(creative.marketing_tone)
    if getattr(creative, "brand_positioning", None):
        themes.append(creative.brand_positioning)

    era: list[str] = []
    era.extend(getattr(creative, "cultural_references", []) or [])
    if getattr(creative, "festival_context", None):
        era.append(creative.festival_context)
    if getattr(creative, "brand_era", None):
        era.append(creative.brand_era)

    sensory: list[str] = []
    if getattr(creative, "visual_style", None):
        sensory.append(str(creative.visual_style))
    if getattr(creative, "color_dominant", None):
        sensory.append(creative.color_dominant)

    return {
        "category": getattr(creative, "category", None),
        "brand": getattr(creative, "brand", None),
        "themes": themes,
        "era_signifiers": era,
        "sensory": sensory,
    }


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
