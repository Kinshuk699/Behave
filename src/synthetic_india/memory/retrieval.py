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
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from synthetic_india.agents.llm_client import get_embedding
from synthetic_india.config import MemoryConfig, get_memory_config
from synthetic_india.schemas.memory import MemoryNode, RetrievalScore

# ── Phase 7 (2026-04-23): query embedding cache ────────────────────────
# Process-local dict keyed on raw query text. Prevents duplicate OpenAI
# `text-embedding-3-small` calls when the same creative is evaluated across
# many personas. Module-level so it survives across evaluate_creative() calls
# but is wiped on process restart (no stale embeddings if we change models).
_QUERY_EMBEDDING_CACHE: dict[str, list[float]] = {}


async def embed_query_cached(query_text: str) -> list[float]:
    """
    Return an embedding for `query_text`, using a process-local cache.

    Looks `get_embedding` up via this module's globals so unit tests can
    monkeypatch `synthetic_india.memory.retrieval.get_embedding` directly.
    """
    cached = _QUERY_EMBEDDING_CACHE.get(query_text)
    if cached is not None:
        return cached
    embedding = await get_embedding(query_text)
    _QUERY_EMBEDDING_CACHE[query_text] = embedding
    return embedding


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

        # Memory strengthening on retrieval — Phase 2 habituation-aware version.
        # Cite: Opus pressure-test Issue #1 (runaway loop); Anshuj v3 Part 5
        # (ACT-R activation + habituation + fading affect bias). The original
        # blind '+0.02 every retrieval' code created a positive feedback loop
        # with no ceiling and no decay. Now: first <=5 retrievals in 7 days
        # strengthen the memory; beyond that, habituation actively dampens.
        for s in scored[:top_k]:
            self._on_retrieval(s.node, now)

        return scored[:top_k]

    # ── Lifecycle constants (Phase 2, 2026-04-21) ─────────────────────
    # All values are conservative starting points. Tune from simulation
    # data (Anshuj v3 Experiment 2) — they are not magic numbers.
    HABITUATION_THRESHOLD: int = 5            # retrievals within window
    HABITUATION_WINDOW_DAYS: int = 7
    HABITUATION_PENALTY: float = 0.03         # arousal -= this when habituated
    STRENGTHENING_DELTA: float = 0.02         # arousal += this when fresh
    IMPORTANCE_DELTA: float = 0.10
    MAX_AROUSAL: float = 1.0
    MIN_AROUSAL_FLOOR: float = 0.15           # never disappear, can revive
    MAX_IMPORTANCE: float = 10.0
    TIMESTAMP_WINDOW_CAP: int = 10            # rolling window size
    DORMANCY_MIN_DAYS: int = 30               # decay starts after this
    DORMANCY_DECAY_RATE: float = 0.005        # arousal lost per daily_decay call
    FADING_AFFECT_POSITIVE_FACTOR: float = 0.5   # positive memories decay slower
    FADING_AFFECT_NEGATIVE_FACTOR: float = 1.5   # negative memories decay faster

    _POSITIVE_THEME_MARKERS: frozenset[str] = frozenset({
        "joyful", "warmth", "nostalgia", "comfort", "pride", "celebration",
        "family_warmth", "tradition", "heritage", "love",
    })
    _NEGATIVE_THEME_MARKERS: frozenset[str] = frozenset({
        "loss", "anxious", "shame", "anger", "fear", "betrayal",
        "regret", "melancholy",
    })

    def _on_retrieval(self, node: MemoryNode, now: datetime) -> None:
        """Update node state after it surfaces in a retrieval result.

        Order matters: append the timestamp FIRST, then count recent ones,
        so the just-fired retrieval is itself part of the habituation count.
        """
        node.last_accessed_at = now
        node.access_count += 1
        node.recent_retrieval_timestamps.append(now)
        # Cap the rolling window (oldest dropped first).
        if len(node.recent_retrieval_timestamps) > self.TIMESTAMP_WINDOW_CAP:
            node.recent_retrieval_timestamps = node.recent_retrieval_timestamps[
                -self.TIMESTAMP_WINDOW_CAP:
            ]

        recent_count = self._count_recent_retrievals(node, now)

        if recent_count > self.HABITUATION_THRESHOLD:
            # Habituated — dampen.
            node.emotional_arousal = max(
                self.MIN_AROUSAL_FLOOR,
                node.emotional_arousal - self.HABITUATION_PENALTY,
            )
        else:
            # Fresh retrieval — strengthen.
            node.emotional_arousal = min(
                self.MAX_AROUSAL,
                node.emotional_arousal + self.STRENGTHENING_DELTA,
            )
            node.importance = min(
                self.MAX_IMPORTANCE,
                node.importance + self.IMPORTANCE_DELTA,
            )

    def _count_recent_retrievals(self, node: MemoryNode, now: datetime) -> int:
        cutoff = now - timedelta(days=self.HABITUATION_WINDOW_DAYS)
        return sum(1 for ts in node.recent_retrieval_timestamps if ts > cutoff)

    def daily_decay(self, node: MemoryNode, now: Optional[datetime] = None) -> None:
        """Apply time-based arousal decay with fading affect bias.

        - Memories accessed in the last DORMANCY_MIN_DAYS are untouched.
        - Older memories lose arousal at DORMANCY_DECAY_RATE per call.
        - Positive-themed memories decay 0.5x as fast (fading affect bias,
          Walker & Skowronski 2009).
        - Negative-themed memories decay 1.5x as fast.
        - Hard floor at MIN_AROUSAL_FLOOR so dormant memories can be revived
          by a strong matching cue rather than vanishing.
        """
        now = now or datetime.utcnow()
        days_since = (now - node.last_accessed_at).total_seconds() / 86400.0
        if days_since < self.DORMANCY_MIN_DAYS:
            return

        themes = {t.lower() for t in (node.key_themes or [])}
        if themes & self._POSITIVE_THEME_MARKERS:
            factor = self.FADING_AFFECT_POSITIVE_FACTOR
        elif themes & self._NEGATIVE_THEME_MARKERS:
            factor = self.FADING_AFFECT_NEGATIVE_FACTOR
        else:
            factor = 1.0

        node.emotional_arousal = max(
            self.MIN_AROUSAL_FLOOR,
            node.emotional_arousal - self.DORMANCY_DECAY_RATE * factor,
        )

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
        # Phase 7 (2026-04-23): pass query_embedding through so the 10% slot can
        # use cosine similarity when both query and memory have embeddings.
        if query_tags:
            return self._structured_relevance(
                node, query_tags, query_embedding=query_embedding
            )

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
        Log-scale retrieval count: ε·log(1 + min(access_count, CAP)).
        Diminishing returns + a hard cap so a single dominator memory cannot
        accumulate unbounded boost from retrieval frequency. Without the cap,
        habituation in arousal is overwhelmed by frequency once a memory has
        been retrieved >10 times, defeating the lifecycle (Phase 2 fix).
        ACT-R / Hou et al. (CHI EA 2024).
        """
        return math.log(1 + min(node.access_count, self._RETRIEVAL_FREQ_CAP))

    _RETRIEVAL_FREQ_CAP: int = 5

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
        query_embedding: Optional[list[float]] = None,
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

        # 10% tiebreaker slot.
        # Phase 7 (2026-04-23): if both query and memory have embeddings, use
        # cosine similarity. Otherwise fall back to the legacy token overlap
        # against the tag blob — preserves backward compatibility for memory
        # nodes seeded before embeddings were wired in.
        token_score = 0.0
        if query_embedding and node.embedding:
            cos = self._cosine_similarity(query_embedding, node.embedding)
            # Cosine on OpenAI embeddings is in [-1, 1]; clamp to [0, 1]
            token_score = max(0.0, cos)
        elif node.embedding_key:
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
