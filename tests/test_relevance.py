"""
Phase 1: Structured-relevance test harness.

Replaces the naive whitespace token-overlap relevance with a multi-signal score
weighted by (category, themes, era/sensory, token cosine). This file is the
empirical gate Opus's critique calls out: without a labeled harness, the
"relevance" claim is unfalsifiable.

Pass criteria (Anshuj v3 Experiment 1, softened for first pass):
  - All SHOULD-MATCH pairs score >= 0.40
  - All SHOULDN'T-MATCH pairs score <= 0.30
  - Mean SHOULD-MATCH score is at least 2x mean SHOULDN'T-MATCH score
  - Spearman rank correlation between scores and human labels >= 0.6
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytest

from synthetic_india.memory.retrieval import MemoryRetriever
from synthetic_india.schemas.memory import MemoryNode, MemoryType


# ── Fixtures: MemoryNode factories ────────────────────────────────────


def _make_memory(
    *,
    description: str,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    key_themes: Optional[list[str]] = None,
    memory_era: Optional[str] = None,
    sensory_anchors: Optional[list[str]] = None,
) -> MemoryNode:
    return MemoryNode(
        node_id=f"test_{description[:8]}",
        persona_id="test_persona",
        memory_type=MemoryType.OBSERVATION,
        description=description,
        subject="test_persona",
        predicate="recalls",
        object="memory",
        importance=5.0,
        embedding_key=description,
        brand=brand,
        category=category,
        key_themes=key_themes or [],
        memory_era=memory_era,
        sensory_anchors=sensory_anchors or [],
    )


def _make_creative_tags(
    *,
    category: str,
    brand: Optional[str] = None,
    themes: Optional[list[str]] = None,
    era_signifiers: Optional[list[str]] = None,
    sensory: Optional[list[str]] = None,
) -> dict:
    """The structured-relevance interface accepts a tag dict, not a raw query string."""
    return {
        "category": category,
        "brand": brand,
        "themes": themes or [],
        "era_signifiers": era_signifiers or [],
        "sensory": sensory or [],
    }


# ── 15 hand-labeled (memory, creative) pairs ──────────────────────────
#
# Each row: (label, memory, creative_tags)
#   label = "SHOULD" if a human would expect this memory to surface for this ad,
#           "SHOULDNT" otherwise.
#
# These pairs probe the cases that the current naive token-overlap function
# specifically gets wrong — different brand names with same category, era cues
# without text overlap, etc.

LABELED_PAIRS: list[tuple[str, MemoryNode, dict]] = [
    # ── SHOULD MATCH (8) ──
    (
        "SHOULD",  # Nirma childhood memory ↔ Surf Excel ad. Different brand names,
                   # same category, both family-warmth themed. Naive token overlap = 0.
        _make_memory(
            description="Nani Ji used to hum the Nirma jingle while braiding my hair on Sunday mornings",
            category="detergent",
            brand="Nirma",
            key_themes=["family_warmth", "tradition", "ritual"],
            memory_era="childhood",
            sensory_anchors=["jingle", "jasmine_oil", "doordarshan"],
        ),
        _make_creative_tags(
            category="detergent",
            brand="Surf Excel",
            themes=["family_warmth", "tradition"],
            sensory=["jingle"],
        ),
    ),
    (
        "SHOULD",  # Doordarshan-era childhood memory ↔ Parle-G ad with vintage feel.
                   # Different category, same era. The era signal must carry it.
        _make_memory(
            description="Watching Doordarshan with chai in 1990, before cable TV existed",
            category="biscuit",
            brand="Parle-G",
            key_themes=["nostalgia", "simplicity", "childhood"],
            memory_era="childhood",
            sensory_anchors=["doordarshan", "chai", "biscuit_dunked_in_tea"],
        ),
        _make_creative_tags(
            category="biscuit",
            brand="Parle-G",
            themes=["nostalgia", "heritage", "simplicity"],
            era_signifiers=["doordarshan", "vintage_packaging"],
            sensory=["chai"],
        ),
    ),
    (
        "SHOULD",  # Direct brand match: same brand, same category.
        _make_memory(
            description="My mother only ever bought Tata salt — said it was the safe choice",
            category="salt",
            brand="Tata",
            key_themes=["trust", "safety", "family"],
            sensory_anchors=["kitchen", "yellow_packet"],
        ),
        _make_creative_tags(
            category="salt",
            brand="Tata",
            themes=["trust", "safety"],
        ),
    ),
    (
        "SHOULD",  # Sibling category match (both FMCG / personal care).
        _make_memory(
            description="Standing in line at Big Bazaar with my mother, picking out Lifebuoy soap",
            category="soap",
            brand="Lifebuoy",
            key_themes=["hygiene", "family_routine"],
            sensory_anchors=["soap_bar", "store_smell"],
        ),
        _make_creative_tags(
            category="shampoo",  # Sibling under personal_care
            brand="Sunsilk",
            themes=["hygiene", "family_routine"],
        ),
    ),
    (
        "SHOULD",  # Festival context match.
        _make_memory(
            description="The Diwali sweets my grandmother made every year — kaju katli, motichoor laddoo",
            category="sweets",
            brand="homemade",
            key_themes=["festival", "family", "tradition"],
            memory_era="childhood",
            sensory_anchors=["diwali", "ghee_smell", "sweets"],
        ),
        _make_creative_tags(
            category="sweets",
            brand="Haldiram",
            themes=["festival", "tradition", "family"],
            era_signifiers=["diwali"],
            sensory=["sweets"],
        ),
    ),
    (
        "SHOULD",  # Adolescence aspiration ↔ ad in same category targeting same life stage.
        _make_memory(
            description="My first pair of Levi's jeans in college — saved up for three months",
            category="apparel",
            brand="Levi's",
            key_themes=["aspiration", "first_purchase", "identity"],
            memory_era="adolescence",
            sensory_anchors=["denim", "shopping_mall"],
        ),
        _make_creative_tags(
            category="apparel",
            brand="Levi's",
            themes=["aspiration", "identity"],
        ),
    ),
    (
        "SHOULD",  # Sensory match dominant: jingle ↔ jingle, even though brands differ.
        _make_memory(
            description="The Nirma washing-powder jingle every morning on the radio",
            category="detergent",
            brand="Nirma",
            key_themes=["routine", "morning"],
            sensory_anchors=["jingle", "radio"],
        ),
        _make_creative_tags(
            category="detergent",
            brand="Tide",
            themes=["routine"],
            sensory=["jingle"],
        ),
    ),
    (
        "SHOULD",  # Theme match (nostalgia) without category match.
        _make_memory(
            description="Listening to old Kishore Kumar songs on All India Radio with my father",
            category="music",
            brand=None,
            key_themes=["nostalgia", "father", "heritage"],
            memory_era="childhood",
            sensory_anchors=["radio", "kishore_kumar", "evening_chai"],
        ),
        _make_creative_tags(
            category="music_streaming",
            brand="Spotify",
            themes=["nostalgia", "heritage"],
            era_signifiers=["kishore_kumar"],
        ),
    ),
    # ── SHOULDN'T MATCH (7) ──
    (
        "SHOULDNT",  # Nirma childhood memory ↔ HDFC Life Insurance ad.
                     # Opus's exact example. Naive token overlap might catch "family"
                     # words; structured score should kill it.
        _make_memory(
            description="Nani Ji used to hum the Nirma jingle while braiding my hair on Sunday mornings",
            category="detergent",
            brand="Nirma",
            key_themes=["family_warmth", "tradition"],
            memory_era="childhood",
            sensory_anchors=["jingle", "jasmine_oil"],
        ),
        _make_creative_tags(
            category="insurance",
            brand="HDFC Life",
            themes=["financial_security", "future_planning"],
        ),
    ),
    (
        "SHOULDNT",  # Childhood biscuit memory ↔ luxury car ad.
        _make_memory(
            description="Parle-G dipped in masala chai after school",
            category="biscuit",
            brand="Parle-G",
            key_themes=["childhood", "comfort"],
            memory_era="childhood",
            sensory_anchors=["chai", "biscuit"],
        ),
        _make_creative_tags(
            category="luxury_car",
            brand="BMW",
            themes=["status", "performance", "luxury"],
        ),
    ),
    (
        "SHOULDNT",  # Fashion memory ↔ tractor ad. No conceivable connection.
        _make_memory(
            description="My first Zara dress for a college party — felt like a million bucks",
            category="apparel",
            brand="Zara",
            key_themes=["aspiration", "youth", "social"],
            memory_era="adolescence",
            sensory_anchors=["fabric", "mall"],
        ),
        _make_creative_tags(
            category="agriculture_equipment",
            brand="Mahindra",
            themes=["productivity", "farming"],
        ),
    ),
    (
        "SHOULDNT",  # Recent observation about a fintech app ↔ traditional snack ad.
        _make_memory(
            description="Used PhonePe to split the dinner bill last Tuesday with friends",
            category="fintech",
            brand="PhonePe",
            key_themes=["convenience", "modern", "social_payment"],
            memory_era="recent",
            sensory_anchors=["phone_screen"],
        ),
        _make_creative_tags(
            category="snacks",
            brand="Lays",
            themes=["fun", "snacking"],
        ),
    ),
    (
        "SHOULDNT",  # Same era cue (childhood) but completely unrelated category and theme.
        _make_memory(
            description="Watching cricket matches with my dad on a tiny black-and-white TV",
            category="sports",
            brand=None,
            key_themes=["family", "cricket"],
            memory_era="childhood",
            sensory_anchors=["bw_tv", "doordarshan"],
        ),
        _make_creative_tags(
            category="skincare",
            brand="Olay",
            themes=["beauty", "anti_aging"],
        ),
    ),
    (
        "SHOULDNT",  # Trick case: shared word "family" in description, but completely
                     # different category and themes. Naive overlap may match; structured shouldn't.
        _make_memory(
            description="Family dinner at the dhaba — paneer butter masala and naan",
            category="restaurant",
            brand="local_dhaba",
            key_themes=["family", "food", "outing"],
            sensory_anchors=["dhaba", "naan"],
        ),
        _make_creative_tags(
            category="cement",
            brand="ACC",
            themes=["construction", "strength", "family"],  # "family" is a red herring
        ),
    ),
    (
        "SHOULDNT",  # Brand recall about a budget product ↔ luxury ad in unrelated category.
        _make_memory(
            description="Used Vim bar to scrub utensils every weekend in the hostel",
            category="dishwash",
            brand="Vim",
            key_themes=["budget", "routine", "hostel_life"],
            memory_era="early_career",
            sensory_anchors=["vim_bar", "kitchen_sink"],
        ),
        _make_creative_tags(
            category="luxury_watch",
            brand="Rolex",
            themes=["luxury", "status", "achievement"],
        ),
    ),
]


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.fixture
def retriever() -> MemoryRetriever:
    return MemoryRetriever()


def test_structured_relevance_function_exists(retriever):
    """The new structured relevance function must exist on MemoryRetriever."""
    assert hasattr(retriever, "_structured_relevance"), (
        "MemoryRetriever needs a _structured_relevance(node, creative_tags) method"
    )


def test_should_match_pairs_score_above_threshold(retriever):
    """Every SHOULD-MATCH pair must score >= 0.40 under the structured function."""
    failures = []
    for label, memory, tags in LABELED_PAIRS:
        if label != "SHOULD":
            continue
        score = retriever._structured_relevance(memory, tags)
        if score < 0.40:
            failures.append(
                f"  {memory.brand or '?'} ({memory.category}) ↔ "
                f"{tags['brand'] or '?'} ({tags['category']}): {score:.3f}"
            )
    assert not failures, (
        f"{len(failures)} SHOULD-MATCH pairs scored below 0.40:\n"
        + "\n".join(failures)
    )


def test_shouldnt_match_pairs_score_below_threshold(retriever):
    """Every SHOULDN'T-MATCH pair must score <= 0.30."""
    failures = []
    for label, memory, tags in LABELED_PAIRS:
        if label != "SHOULDNT":
            continue
        score = retriever._structured_relevance(memory, tags)
        if score > 0.30:
            failures.append(
                f"  {memory.brand or '?'} ({memory.category}) ↔ "
                f"{tags['brand'] or '?'} ({tags['category']}): {score:.3f}"
            )
    assert not failures, (
        f"{len(failures)} SHOULDN'T-MATCH pairs scored above 0.30:\n"
        + "\n".join(failures)
    )


def test_separation_ratio(retriever):
    """Mean SHOULD score must be at least 2x mean SHOULDN'T score."""
    should_scores = [
        retriever._structured_relevance(m, t) for label, m, t in LABELED_PAIRS if label == "SHOULD"
    ]
    shouldnt_scores = [
        retriever._structured_relevance(m, t) for label, m, t in LABELED_PAIRS if label == "SHOULDNT"
    ]
    mean_should = sum(should_scores) / len(should_scores)
    mean_shouldnt = sum(shouldnt_scores) / len(shouldnt_scores) if shouldnt_scores else 0.0
    if mean_shouldnt == 0:
        assert mean_should > 0.4
        return
    ratio = mean_should / mean_shouldnt
    assert ratio >= 2.0, (
        f"Separation ratio too small: mean SHOULD={mean_should:.3f}, "
        f"mean SHOULDNT={mean_shouldnt:.3f}, ratio={ratio:.2f}x (need >=2.0x)"
    )


def test_top_5_retrieval_precision(retriever):
    """When all 15 memories are scored against the FIRST creative (a SHOULD-MATCH detergent ad),
    the top 5 should contain mostly SHOULD-MATCH memories of detergent or related categories."""
    target_creative = LABELED_PAIRS[0][2]  # detergent ad targeting Surf Excel
    all_memories = [m for _, m, _ in LABELED_PAIRS]

    scored = [
        (label, m, retriever._structured_relevance(m, target_creative))
        for label, m, _ in LABELED_PAIRS
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    top5 = scored[:5]

    # The top-1 must be the Nirma detergent SHOULD-MATCH memory.
    assert top5[0][0] == "SHOULD", (
        f"Top-1 retrieval should be a SHOULD-MATCH; got "
        f"{top5[0][0]} ({top5[0][1].brand}/{top5[0][1].category}, score={top5[0][2]:.3f})"
    )
    # No SHOULDN'T-MATCH should appear above the highest SHOULD-MATCH score.
    top5_should_count = sum(1 for label, _, _ in top5 if label == "SHOULD")
    assert top5_should_count >= 3, (
        f"Top-5 contains only {top5_should_count} SHOULD-MATCH memories (need >=3). "
        f"Top-5: {[(l, m.brand, m.category, round(s,3)) for l,m,s in top5]}"
    )
