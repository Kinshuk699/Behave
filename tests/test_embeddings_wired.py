"""
Phase 7 — Embeddings actually wired into structured relevance.

Phase 1 added the structured-relevance formula:
    Score = 0.40·category + 0.30·themes + 0.20·era_or_sensory + 0.10·token

The 0.10 slot uses keyword token overlap. In production this is the only
signal that ever runs, because memory nodes have `embedding: null` and
the evaluator never computed query embeddings. This phase fixes both:

  1. `_structured_relevance` accepts an optional `query_embedding`.
     If both query AND node have embeddings, the 0.10 slot uses cosine
     similarity instead of token overlap. Token fallback preserved.
  2. `evaluate_creative(use_embeddings=True)` actually calls
     `get_embedding()` on the query text and threads it through.
  3. `_query_embedding_cache` deduplicates calls — the same creative
     query text triggers exactly one OpenAI call per process.
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, patch

import pytest


# ── Unit: cosine slot in structured relevance ────────────────


def _make_node(**overrides):
    """Build a MemoryNode for testing without dragging in fixtures."""
    from synthetic_india.schemas.memory import MemoryNode, MemoryType

    base = dict(
        node_id="n_test",
        persona_id="p_test",
        memory_type=MemoryType.OBSERVATION,
        description="Saw a Nirma detergent ad on Doordarshan as a child.",
        subject="test_persona",
        predicate="recalls",
        object="ad",
        embedding_key="nirma detergent doordarshan childhood",
        category="detergent",
        brand="Nirma",
        key_themes=["nostalgia", "value_for_money"],
        memory_era="1990s",
        sensory_anchors=["Hema Hemamalini jingle", "yellow packet"],
        importance=8.0,
        emotional_arousal=0.85,
    )
    base.update(overrides)
    return MemoryNode(**base)


class TestStructuredRelevanceUsesEmbeddings:
    def test_cosine_used_when_both_embeddings_present(self):
        """When query_embedding and node.embedding both exist, 10% slot uses cosine."""
        from synthetic_india.memory.retrieval import MemoryRetriever

        retriever = MemoryRetriever()
        node = _make_node(embedding=[1.0, 0.0, 0.0])
        tags = {
            "category": "detergent",
            "themes": ["nostalgia"],
            "era_signifiers": ["1990s"],
            "sensory": [],
        }

        # Identical embeddings → cosine = 1.0; should max out the 10% slot
        score_with_emb = retriever._structured_relevance(
            node, tags, query_embedding=[1.0, 0.0, 0.0]
        )
        # Orthogonal embeddings → cosine = 0.0
        score_orthogonal = retriever._structured_relevance(
            node, tags, query_embedding=[0.0, 1.0, 0.0]
        )
        # Non-trivial difference proves the embedding actually moved the score
        assert score_with_emb > score_orthogonal, (
            f"identical-emb score {score_with_emb} should beat orthogonal {score_orthogonal}"
        )

    def test_token_fallback_when_no_embeddings(self):
        """Backward compat: when embeddings absent, token fallback runs."""
        from synthetic_india.memory.retrieval import MemoryRetriever

        retriever = MemoryRetriever()
        node = _make_node()  # no embedding
        tags = {
            "category": "detergent",
            "themes": ["nostalgia"],
            "era_signifiers": [],
            "sensory": [],
        }
        # Should not raise; should still produce a score from category + themes
        score = retriever._structured_relevance(node, tags, query_embedding=None)
        assert score > 0.0

    def test_token_used_when_only_query_emb_missing(self):
        """If node has embedding but query doesn't, fall back to tokens."""
        from synthetic_india.memory.retrieval import MemoryRetriever

        retriever = MemoryRetriever()
        node = _make_node(embedding=[1.0, 0.0, 0.0])
        tags = {"category": "detergent", "themes": [], "era_signifiers": [], "sensory": []}
        score = retriever._structured_relevance(node, tags, query_embedding=None)
        # category match (0.4 * 1.0) = 0.40 floor
        assert score >= 0.40

    def test_default_query_embedding_param_is_optional(self):
        """Existing call sites without the new arg keep working."""
        from synthetic_india.memory.retrieval import MemoryRetriever

        retriever = MemoryRetriever()
        node = _make_node()
        tags = {"category": "detergent", "themes": [], "era_signifiers": [], "sensory": []}
        # No query_embedding kwarg → must not raise
        score = retriever._structured_relevance(node, tags)
        assert 0.0 <= score <= 1.0


# ── Threading: _score_relevance passes query_embedding through ──


class TestScoreRelevanceThreadsEmbedding:
    def test_score_relevance_passes_embedding_into_structured(self):
        """When tags AND embeddings present, both should reach _structured_relevance."""
        from synthetic_india.memory.retrieval import MemoryRetriever

        retriever = MemoryRetriever()
        node = _make_node(embedding=[1.0, 0.0, 0.0])
        tags = {"category": "detergent", "themes": [], "era_signifiers": [], "sensory": []}

        # Cosine path: identical query_embedding produces a non-zero token-slot
        identical = retriever._score_relevance(
            node, query_embedding=[1.0, 0.0, 0.0], query_text=None, query_tags=tags
        )
        orthogonal = retriever._score_relevance(
            node, query_embedding=[0.0, 1.0, 0.0], query_text=None, query_tags=tags
        )
        assert identical > orthogonal


# ── Caching: query embedding fetched once per text ──────────


class TestQueryEmbeddingCache:
    def test_same_text_calls_get_embedding_once(self):
        """Cache must dedupe calls for the same query text."""
        from synthetic_india.memory import retrieval as retrieval_mod

        # Ensure cache is empty for the test text
        cache_key = "PHASE7-test-creative-query-text"
        retrieval_mod._QUERY_EMBEDDING_CACHE.pop(cache_key, None)

        with patch(
            "synthetic_india.memory.retrieval.get_embedding",
            new=AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ) as mock_embed:
            import asyncio

            async def run():
                a = await retrieval_mod.embed_query_cached(cache_key)
                b = await retrieval_mod.embed_query_cached(cache_key)
                return a, b

            a, b = asyncio.get_event_loop().run_until_complete(run()) \
                if False else asyncio.run(run())

        assert a == [0.1, 0.2, 0.3]
        assert a == b
        assert mock_embed.call_count == 1, (
            f"expected 1 call (cached); got {mock_embed.call_count}"
        )

    def test_different_text_calls_get_embedding_each(self):
        from synthetic_india.memory import retrieval as retrieval_mod

        retrieval_mod._QUERY_EMBEDDING_CACHE.clear()

        with patch(
            "synthetic_india.memory.retrieval.get_embedding",
            new=AsyncMock(side_effect=[[1.0], [2.0]]),
        ) as mock_embed:
            import asyncio

            async def run():
                a = await retrieval_mod.embed_query_cached("PHASE7-text-A")
                b = await retrieval_mod.embed_query_cached("PHASE7-text-B")
                return a, b

            a, b = asyncio.run(run())

        assert a == [1.0]
        assert b == [2.0]
        assert mock_embed.call_count == 2


# ── Integration: evaluate_creative wires use_embeddings=True ──


class TestEvaluateCreativeUsesEmbeddings:
    def test_use_embeddings_true_calls_embed_query_cached(self):
        """When use_embeddings=True, evaluate_creative must compute query embedding."""
        from synthetic_india.agents import persona_evaluator

        # Confirms the helper is actually imported/used in persona_evaluator
        # (cheap structural test — full async run requires network).
        import inspect

        src = inspect.getsource(persona_evaluator.evaluate_creative)
        assert "embed_query_cached" in src, (
            "evaluate_creative should call embed_query_cached when use_embeddings=True"
        )
        assert "use_embeddings" in src
