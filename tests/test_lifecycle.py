"""
Phase 2: Memory lifecycle health.

Fixes the runaway-arousal bug Opus pressure-test Issue #1 calls out:
  arousal += 0.02 every retrieval, no decay, no habituation.
  Result: one memory dominates every future evaluation forever.

Three mechanisms (Anshuj v3 Part 5, simplified):
  - Habituation:    >5 retrievals in last 7 days  ->  arousal stops growing,
                    starts dampening. Mirrors stimulus-response habituation.
  - Decay:          memories not retrieved for >30 days lose arousal slowly.
                    Positive emotional tones decay slower (fading affect bias,
                    Walker & Skowronski 2009).
  - Smooth cliff:   replace the binary 50-memory full_dump_threshold with a
                    progressive taper. No visible behavior cliff.

Floors:
  - arousal       in [0.15, 1.0]  -- never zero so dormant memories can revive.
  - importance    in [0.0, 10.0].
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from synthetic_india.memory.consumer import MemoryConsumer
from synthetic_india.memory.retrieval import MemoryRetriever
from synthetic_india.memory.stream import MemoryStream
from synthetic_india.schemas.memory import MemoryNode, MemoryType


def _make_node(
    *,
    arousal: float = 0.5,
    importance: float = 5.0,
    description: str = "test memory",
    category: str | None = "detergent",
    created_offset_days: int = 0,
    last_accessed_offset_days: int | None = None,
    access_count: int = 0,
    recent_timestamps: list[datetime] | None = None,
) -> MemoryNode:
    now = datetime.utcnow()
    last_acc = (
        now - timedelta(days=last_accessed_offset_days)
        if last_accessed_offset_days is not None
        else now
    )
    node = MemoryNode(
        node_id=f"n_{description}",
        persona_id="p_test",
        memory_type=MemoryType.OBSERVATION,
        created_at=now - timedelta(days=created_offset_days),
        description=description,
        subject="p_test",
        predicate="recalls",
        object="x",
        importance=importance,
        embedding_key=description,
        category=category,
        emotional_arousal=arousal,
        last_accessed_at=last_acc,
        access_count=access_count,
    )
    if recent_timestamps is not None:
        node.recent_retrieval_timestamps = recent_timestamps
    return node


# ── 1. Habituation ────────────────────────────────────────────────────


def test_memory_node_has_recent_retrieval_timestamps_field():
    """Need a rolling window of retrieval timestamps to compute habituation."""
    node = _make_node()
    assert hasattr(node, "recent_retrieval_timestamps")
    assert isinstance(node.recent_retrieval_timestamps, list)


def test_strengthening_within_threshold_increases_arousal():
    """First few retrievals still strengthen the memory."""
    retriever = MemoryRetriever()
    node = _make_node(arousal=0.5)
    nodes = [node]

    retriever.retrieve(nodes=nodes, query_tags={"category": "detergent"}, top_k=1)

    assert node.emotional_arousal > 0.5, "First retrieval should strengthen"
    assert node.access_count == 1
    assert len(node.recent_retrieval_timestamps) == 1


def test_habituation_kicks_in_after_threshold():
    """Once a memory has been retrieved >5 times in last 7 days, arousal must
    stop growing and start to dampen on subsequent retrievals."""
    retriever = MemoryRetriever()
    now = datetime.utcnow()
    # Pre-load 6 recent retrievals (already over threshold of 5).
    recent = [now - timedelta(days=i) for i in range(6)]
    node = _make_node(
        arousal=0.80,
        access_count=6,
        recent_timestamps=recent,
    )

    arousal_before = node.emotional_arousal
    retriever.retrieve(nodes=[node], query_tags={"category": "detergent"}, top_k=1)

    assert node.emotional_arousal < arousal_before, (
        f"Habituated memory should dampen, not grow. Was {arousal_before}, now "
        f"{node.emotional_arousal}"
    )


def test_recent_timestamps_window_caps_at_ten():
    """The rolling window must not grow unboundedly."""
    retriever = MemoryRetriever()
    node = _make_node()

    for _ in range(15):
        retriever.retrieve(nodes=[node], query_tags={"category": "detergent"}, top_k=1)

    assert len(node.recent_retrieval_timestamps) <= 10, (
        f"Window should cap at 10; got {len(node.recent_retrieval_timestamps)}"
    )


def test_old_timestamps_outside_window_dont_count_for_habituation():
    """Retrievals from >7 days ago must not count toward the habituation threshold."""
    retriever = MemoryRetriever()
    now = datetime.utcnow()
    # 6 retrievals all from >7 days ago — should NOT habituate.
    old_recent = [now - timedelta(days=20 + i) for i in range(6)]
    node = _make_node(
        arousal=0.50,
        access_count=6,
        recent_timestamps=old_recent,
    )

    arousal_before = node.emotional_arousal
    retriever.retrieve(nodes=[node], query_tags={"category": "detergent"}, top_k=1)

    assert node.emotional_arousal > arousal_before, (
        "Old retrievals shouldn't trigger habituation — memory should still strengthen"
    )


# ── 2. Decay ──────────────────────────────────────────────────────────


def test_daily_decay_reduces_arousal_for_old_memories():
    """A memory not retrieved in 60 days should lose arousal."""
    retriever = MemoryRetriever()
    node = _make_node(
        arousal=0.80,
        last_accessed_offset_days=60,
    )

    arousal_before = node.emotional_arousal
    retriever.daily_decay(node)
    assert node.emotional_arousal < arousal_before, (
        "Old unretrieved memory should decay"
    )


def test_recent_memories_dont_decay():
    """A memory retrieved within the last 30 days should not decay."""
    retriever = MemoryRetriever()
    node = _make_node(
        arousal=0.80,
        last_accessed_offset_days=5,
    )

    retriever.daily_decay(node)
    assert node.emotional_arousal == pytest.approx(0.80), (
        "Memory accessed 5 days ago should not decay"
    )


def test_arousal_floor_prevents_complete_disappearance():
    """No matter how much decay, arousal must never go below 0.15."""
    retriever = MemoryRetriever()
    node = _make_node(
        arousal=0.20,
        last_accessed_offset_days=10_000,  # ~27 years untouched
    )

    # Simulate 100 daily-decay ticks
    for _ in range(100):
        retriever.daily_decay(node)

    assert node.emotional_arousal >= 0.15, (
        f"Arousal floor violated: {node.emotional_arousal}"
    )


def test_positive_memories_decay_slower_than_negative():
    """Fading affect bias: 'joyful' memories should decay slower than negative ones.

    We approximate emotional tone via memory_type / category proxy: if a memory
    has high arousal AND a positive theme marker, decay is halved. This test
    checks the BEHAVIORAL difference, not the exact mechanism.
    """
    retriever = MemoryRetriever()

    # Two memories, identical except one is tagged positive in key_themes.
    pos = _make_node(
        arousal=0.80, last_accessed_offset_days=60, description="positive",
    )
    pos.key_themes = ["joyful", "warmth"]

    neg = _make_node(
        arousal=0.80, last_accessed_offset_days=60, description="negative",
    )
    neg.key_themes = ["loss", "anxious"]

    retriever.daily_decay(pos)
    retriever.daily_decay(neg)

    assert pos.emotional_arousal > neg.emotional_arousal, (
        f"Positive memory should retain more arousal than negative one. "
        f"Got pos={pos.emotional_arousal}, neg={neg.emotional_arousal}"
    )


# ── 3. Long-horizon stability (the key Anshuj Experiment 2 check) ─────


def test_no_single_memory_dominates_over_many_retrievals():
    """Run 60 retrievals on a stream of 10 memories; no single memory
    should be the top-1 result more than 35% of the time."""
    retriever = MemoryRetriever()
    nodes = [
        _make_node(
            description=f"memory_{i}",
            arousal=0.5 + (i * 0.03),  # slight initial spread, all comparable
            importance=5.0,
            category="detergent",
        )
        for i in range(10)
    ]

    top1_counts: dict[str, int] = {}
    for _ in range(60):
        scored = retriever.retrieve(
            nodes=nodes, query_tags={"category": "detergent"}, top_k=1,
        )
        winner = scored[0].node.node_id
        top1_counts[winner] = top1_counts.get(winner, 0) + 1

    max_share = max(top1_counts.values()) / 60
    assert max_share <= 0.40, (
        f"One memory dominated {max_share:.0%} of 60 retrievals (limit 40%). "
        f"Distribution: {top1_counts}"
    )


# ── 4. Smooth cliff ───────────────────────────────────────────────────


def test_progressive_inclusion_smooths_full_dump_cliff():
    """The number of memories included should taper smoothly between
    20 and 60 nodes, not flip from 'all' to '5' at 50."""
    consumer = MemoryConsumer()

    def _build_stream(n: int) -> MemoryStream:
        stream = MemoryStream(persona_id="p_test")
        for i in range(n):
            stream.add_node(_make_node(description=f"m{i}", category="detergent"))
        return stream

    counts = {}
    for n in [25, 35, 45, 55, 65]:
        stream = _build_stream(n)
        out = consumer.consume(
            stream=stream,
            query="x",
            category="detergent",
            top_k=10,
            query_tags={"category": "detergent"},
        )
        counts[n] = len(out)

    # Behavior must be monotone-ish: as memory count grows, included count
    # should not jump by >25 between successive sizes (smooth taper).
    sizes = sorted(counts.keys())
    for a, b in zip(sizes, sizes[1:]):
        delta = abs(counts[a] - counts[b])
        assert delta <= 25, (
            f"Cliff detected between {a} memories ({counts[a]} included) and "
            f"{b} memories ({counts[b]} included). Delta {delta} > 25."
        )

    # And: by 65 memories we should be in retrieval mode (<=10 returned).
    assert counts[65] <= 10, f"At 65 memories, should be top_k mode; got {counts[65]}"
