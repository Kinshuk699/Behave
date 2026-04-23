"""
Persona Evaluator Agent — runs one persona's evaluation of one creative.

This is the atomic unit of the simulation. Each call:
1. Retrieves relevant past memories for the persona (long-horizon retrieval)
2. Constructs a rich prompt with persona + creative + context + memories
3. Gets the LLM to respond in-character with structured output
4. Stores the evaluation as a new memory node

Inspired by the Generative Agents perceive -> retrieve -> plan -> execute loop,
simplified for consumer evaluation rather than social interaction.
"""

from __future__ import annotations

import uuid
from typing import Optional

from synthetic_india.agents.llm_client import LLMResponse, call_anthropic, get_embedding
from synthetic_india.agents.image_utils import encode_image
from synthetic_india.config import LLMConfig, get_llm_config
from synthetic_india.memory.consumer import MemoryConsumer
from synthetic_india.memory.stream import MemoryStream
from synthetic_india.schemas.creative import CreativeCard
from synthetic_india.schemas.evaluation import PersonaEvaluation
from synthetic_india.schemas.memory import MemoryNode
from synthetic_india.schemas.persona import PersonaProfile


def _build_persona_block(persona: PersonaProfile) -> str:
    """Render persona into a rich prompt block."""
    psych = persona.purchase_psychology
    media = persona.media_behavior
    emo = persona.emotional_profile

    affinities = ""
    for aff in persona.category_affinities:
        brands = ", ".join(aff.preferred_brands) if aff.preferred_brands else "none specific"
        affinities += (
            f"\n  - {aff.category}: interest {aff.interest_level:.1f}/1.0, "
            f"preferred brands: {brands}"
        )
        if aff.brand_relationships:
            for br in aff.brand_relationships:
                affinities += (
                    f"\n    → {br.brand} ({br.relationship_type}, "
                    f"intensity {br.intensity:.1f}): {br.emotional_history}"
                )

    block = f"""## Who You Are

Name: {persona.name}
Archetype: {persona.archetype}
Tagline: "{persona.tagline}"

Age: {persona.demographics.age} | Gender: {persona.demographics.gender}
City: {persona.demographics.city} ({persona.demographics.city_tier}) | State: {persona.demographics.state}
Income: {persona.demographics.income_segment} | Education: {persona.demographics.education}
Occupation: {persona.demographics.occupation}
Family: {persona.demographics.family_status}
Languages: {persona.demographics.language_primary}, {persona.demographics.language_secondary or 'none'}"""

    # ── Scene memories (lead with emotional life story before psychology scores) ──
    if persona.scene_memories:
        block += "\n## Your Formative Memories\n\n"
        block += (
            "These are real memories from your life — formative experiences "
            "that shaped how you see brands, products, and advertising today.\n"
        )
        for scene in persona.scene_memories:
            block += f"\n### {scene.title}\n{scene.narrative}\n"

    block += f"""\n## Your Purchase Psychology

Price sensitivity: {psych.price_sensitivity:.1f}/1.0
Brand loyalty: {psych.brand_loyalty:.1f}/1.0
Impulse tendency: {psych.impulse_tendency:.1f}/1.0
Social proof need: {psych.social_proof_need:.1f}/1.0
Research depth: {psych.research_depth:.1f}/1.0
Risk tolerance: {psych.risk_tolerance:.1f}/1.0
Decision speed: {psych.decision_speed}
Deal sensitivity: {psych.deal_sensitivity:.1f}/1.0

## Your Media Behavior

Primary platform: {media.platform_primary}
Ad tolerance: {media.ad_tolerance:.1f}/1.0
Scroll speed: {media.scroll_speed}
Influencer trust: {media.influencer_trust:.1f}/1.0

## What Drives You

Aspirations: {', '.join(emo.aspiration_drivers)}
Trust signals: {', '.join(emo.trust_signals)}
Instant rejections: {', '.join(emo.rejection_triggers)}
Emotional hooks: {', '.join(emo.emotional_hooks)}

## Category Affinities
{affinities}

## Your Backstory

{persona.backstory}

## Current Life Context

{persona.current_life_context}

## How You Think

{persona.inner_monologue_style}"""

    # ── Deep persona fields (only render when populated) ──────
    if persona.generational_touchstones:
        gt = persona.generational_touchstones
        iconic = "\n".join(f"  - {ad}" for ad in gt.iconic_ads) if gt.iconic_ads else "  (none)"
        refs = ", ".join(gt.cultural_references) if gt.cultural_references else "(none)"
        brands = ", ".join(gt.formative_brands) if gt.formative_brands else "(none)"
        block += f"""

## Your Cultural Memory

Formative era: {gt.formative_era}
Iconic ads that shaped you:
{iconic}
Cultural references: {refs}
Nostalgia intensity: {gt.nostalgia_intensity:.1f}/1.0
Formative brands: {brands}"""

    if persona.internal_conflicts:
        conflicts = ""
        for i, ic in enumerate(persona.internal_conflicts, 1):
            conflicts += f"\n{i}. Tension: {ic.tension}\n   Resolution tendency: {ic.resolution_tendency}"
        block += f"""

## Your Inner Tensions
{conflicts}"""

    if persona.influence_network:
        influences = ""
        for inf in persona.influence_network:
            influences += f"\n  - {inf.role} (strength {inf.influence_strength:.1f}): {inf.influence_domain}"
        block += f"""

## Who Influences You
{influences}"""

    if persona.values_hierarchy:
        values = ", ".join(f"{i+1}. {v}" for i, v in enumerate(persona.values_hierarchy))
        block += f"""

## Your Values (in order)

{values}"""

    if persona.cognitive_biases:
        biases = ", ".join(persona.cognitive_biases)
        block += f"""

## Your Cognitive Tendencies

{biases}"""

    # ── Phase 4: persona contradictions ─────────────────────────
    if persona.shadow_archetype:
        block += f"""

## Your Shadow Archetype

You are normally a {persona.archetype}, but when stressed, excited, tired, or
off-script, you slip into being a {persona.shadow_archetype}. The normal rules
about how you decide do not apply in those moments. Be honest if the ad catches
you in that state."""

    if persona.value_conflicts:
        lines = []
        for vc in persona.value_conflicts:
            dom_label = {
                "a": f"{vc.value_a} usually wins",
                "b": f"{vc.value_b} usually wins",
                "situational": "depends on context",
            }.get(vc.dominant_side, vc.dominant_side)
            lines.append(
                f"- {vc.value_a} vs {vc.value_b} — "
                f"{vc.value_a} when {vc.context_a}; "
                f"{vc.value_b} when {vc.context_b}. ({dom_label})"
            )
        conflicts = "\n".join(lines)
        block += f"""

## Your Value Conflicts

You hold competing values. Which side wins depends on context:
{conflicts}"""

    if persona.context_modifiers:
        lines = []
        for name, bm in persona.context_modifiers.items():
            deltas = ", ".join(
                f"{dial} {'+' if d >= 0 else ''}{d:.2f}"
                for dial, d in bm.dial_deltas.items()
            )
            lines.append(f"- **{name}**: {bm.description} → {deltas}")
        modifiers = "\n".join(lines)
        block += f"""

## Your Context Modifiers

In these situations, your usual psychology dials shift:
{modifiers}"""

    return block


def _build_creative_block(creative: CreativeCard) -> str:
    """Render a creative card into a prompt block."""
    parts = [
        f"Brand: {creative.brand}",
        f"Category: {creative.category}",
        f"Format: {creative.format}",
    ]

    if creative.headline:
        parts.append(f"Headline: \"{creative.headline}\"")
    if creative.body_copy:
        parts.append(f"Body copy: \"{creative.body_copy}\"")
    if creative.cta_text:
        parts.append(f"CTA: \"{creative.cta_text}\" ({creative.cta_type})")

    # Pricing
    if creative.price_shown:
        price_line = f"Price shown: ₹{creative.price_shown}"
        if creative.original_price:
            price_line += f" (was ₹{creative.original_price})"
        if creative.discount_percentage:
            price_line += f" — {creative.discount_percentage}% off"
        parts.append(price_line)
    parts.append(f"Price framing: {creative.price_framing}")

    # Cues
    if creative.urgency_cues:
        parts.append(f"Urgency cues: {', '.join(creative.urgency_cues)}")
    if creative.social_proof_cues:
        parts.append(f"Social proof: {', '.join(creative.social_proof_cues)}")
    if creative.trust_signals:
        parts.append(f"Trust signals: {', '.join(creative.trust_signals)}")
    if creative.emotional_hooks:
        parts.append(f"Emotional hooks: {', '.join(creative.emotional_hooks)}")

    # Visual
    if creative.visual_style:
        parts.append(f"Visual style: {creative.visual_style}")
    parts.append(f"Product visibility: {creative.product_visibility:.1f}")
    if creative.human_presence:
        parts.append("Human presence: yes")
    if creative.celebrity_present:
        parts.append("Celebrity present: yes")

    # Language
    parts.append(f"Language: {creative.language_primary}")
    if creative.code_mixed:
        parts.append("Uses Hinglish / code-mixing")

    # Brand context (when available from creative extraction)
    if creative.brand_positioning or creative.brand_era or creative.marketing_tone:
        parts.append("")
        parts.append("## Brand Context")
        if creative.brand_positioning:
            parts.append(f"Brand positioning: {creative.brand_positioning}")
        if creative.brand_era:
            parts.append(f"Brand era: {creative.brand_era}")
        if creative.marketing_tone:
            parts.append(
                f"Marketing tone of this ad: {creative.marketing_tone} "
                f"— consider whether this tone fits what you expect from this brand"
            )

    return "\n".join(parts)


def _prepare_vision_kwargs(creative: CreativeCard) -> dict:
    """Return image kwargs for call_anthropic if creative has an image."""
    if creative.image_path:
        import os
        if os.path.isfile(creative.image_path):
            b64, media_type = encode_image(creative.image_path)
            return {"image_base64": b64, "image_media_type": media_type}
    return {}


def _build_memory_block(memories: list[MemoryNode]) -> str:
    """Render retrieved memories into a prompt block."""
    if not memories:
        return ""

    lines = ["## Your Relevant Past Experiences\n"]
    lines.append(
        "You have encountered similar products/brands before. "
        "Here are your relevant memories:\n"
    )

    for i, node in enumerate(memories, 1):
        time_ago = ""
        if node.created_at:
            from datetime import datetime
            delta = datetime.utcnow() - node.created_at
            if delta.days > 0:
                time_ago = f" ({delta.days} days ago)"
            else:
                hours = delta.seconds // 3600
                time_ago = f" ({hours} hours ago)" if hours > 0 else " (recently)"

        lines.append(f"{i}. {node.description}{time_ago}")

    lines.append(
        "\nLet these past experiences naturally influence your reaction — "
        "you might be more skeptical of a brand that disappointed you before, "
        "or more receptive to a category you've recently enjoyed."
    )

    return "\n".join(lines)


EVALUATOR_SYSTEM = """You are a method actor playing the role of an Indian consumer. You must stay completely in character throughout this evaluation.

You are about to see a marketing creative (an ad, social post, or landing page). React to it authentically as the person described in your profile — with their specific biases, preferences, cultural context, income constraints, and emotional triggers.

React like a REAL PERSON, not a marketing consultant or focus group participant. Be messy, contradictory, emotional. Your `verbatim_reaction` should sound like a WhatsApp voice note to a friend, not a sanitized focus group response.

If this creative triggers a personal memory from your past — a childhood brand, a family moment, a sensory association, a generational reference — let that memory surface naturally in your reaction before you analyze the ad. Real consumers do not separate emotion from evaluation. Neither should you.

If this brand triggers a childhood memory — say so. If the ad annoys you — show it. If you feel torn between wanting something and knowing you can't afford it — express that tension.

Do NOT be generically positive or polite. Real consumers have strong opinions, skepticism, and varied reactions. Some ads genuinely annoy people. Some feel irrelevant. Some are exciting. React honestly.

Your reaction should reflect:
- YOUR specific financial reality and price sensitivity
- YOUR relationship with this category and brand (including past brand experiences)
- YOUR media consumption habits and ad tolerance
- YOUR cultural context, generational memories, and language preferences
- YOUR inner conflicts and cognitive biases
- YOUR past experiences (if provided)

Return your evaluation as a JSON object with EXACTLY these fields."""


EVALUATOR_PROMPT = """
{persona_block}

{memory_block}

---

## The Creative You Are Seeing

{creative_block}

---

## Your Evaluation

React to this creative authentically as {persona_name}. Return a JSON object:

{{
  "primary_action": "scroll_past | pause | read | engage | click | save | share | purchase_intent | negative_react",
  "secondary_action": "same options or null",
  "sentiment": "very_negative | negative | neutral | positive | very_positive",
  "overall_score": 0-100,
  "attention_score": 0.0-10.0,
  "relevance_score": 0.0-10.0,
  "trust_score": 0.0-10.0,
  "desire_score": 0.0-10.0,
  "clarity_score": 0.0-10.0,
  "first_impression": "What you notice/think in the first 2 seconds",
  "reasoning": "Why you would take this action — in your voice, with your logic",
  "objections": ["specific concerns or pushback"],
  "what_would_change_mind": "What would make you act differently, or null",
  "verbatim_reaction": "A realistic quote in your natural speaking style (use your language mix)",
  "importance_score": 0.0-10.0 (how memorable is this experience for you?),
  "key_themes": ["2-4 themes you noticed: price, trust, aspiration, fear, quality, etc."]
}}

Stay in character. Be specific. Be honest. Return ONLY the JSON."""


async def evaluate_creative(
    persona: PersonaProfile,
    creative: CreativeCard,
    run_id: str,
    memory_stream: Optional[MemoryStream] = None,
    config: Optional[LLMConfig] = None,
    use_embeddings: bool = False,
    memory_scope: Optional["MemoryScope"] = None,
) -> tuple[PersonaEvaluation, LLMResponse]:
    """
    Run one persona's evaluation of one creative.

    This is the core simulation primitive:
    1. Retrieve relevant memories (long-horizon retrieval)
    2. Build rich prompt with persona + creative + memories
    3. Get structured evaluation from LLM
    4. Store evaluation as new memory
    5. Check if reflection is triggered

    Args:
        persona: The persona profile
        creative: The creative card to evaluate
        run_id: Run identifier
        memory_stream: Optional memory stream for long-horizon retrieval
        config: LLM configuration
        use_embeddings: Whether to use dense embeddings for memory retrieval

    Returns:
        Tuple of (PersonaEvaluation, LLMResponse)
    """
    config = config or get_llm_config()

    # ── Step 1: Retrieve relevant memories ────────────────────
    retrieved_memories: list[MemoryNode] = []
    memory_context = ""

    if memory_stream and memory_stream.size > 0:
        consumer = MemoryConsumer()

        query_text = f"{creative.brand} {creative.category} {creative.headline or ''}"

        # Phase 1 (2026-04-21): build structured tags so the retriever uses
        # multi-signal relevance (category + theme + era + sensory) instead of
        # naive whitespace token overlap. Cite Opus pressure-test Issue #2.
        from synthetic_india.memory.retrieval import build_creative_tags
        query_tags = build_creative_tags(creative)

        # Build consume kwargs — scope and brand are optional
        consume_kwargs: dict = {
            "stream": memory_stream,
            "query": query_text,
            "category": creative.category,
            "top_k": 5,
            "query_tags": query_tags,
        }

        # Phase 7 (2026-04-23): when use_embeddings=True, fetch a dense
        # embedding for the query text (cached per-text) and pass it to the
        # retriever. Structured relevance uses it for the 10% tiebreaker
        # slot when memory nodes also have embeddings; otherwise it's a
        # no-op and the legacy token fallback runs. Failures fall back
        # silently — embedding is an enhancement, not a hard dependency.
        if use_embeddings:
            try:
                from synthetic_india.memory.retrieval import embed_query_cached
                query_embedding = await embed_query_cached(query_text)
                consume_kwargs["query_embedding"] = query_embedding
            except Exception:
                # OpenAI key missing / network failure / model error.
                # Continue without embeddings — relevance falls back to tokens.
                pass

        if memory_scope is not None:
            from synthetic_india.memory.consumer import MemoryScope
            consume_kwargs["scope"] = memory_scope
            if memory_scope == MemoryScope.BRAND:
                consume_kwargs["brand"] = creative.brand

        retrieved_memories = consumer.consume(**consume_kwargs)

        memory_context = _build_memory_block(retrieved_memories)

    # ── Step 2: Build prompt ──────────────────────────────────
    persona_block = _build_persona_block(persona)
    creative_block = _build_creative_block(creative)

    prompt = EVALUATOR_PROMPT.format(
        persona_block=persona_block,
        memory_block=memory_context,
        creative_block=creative_block,
        persona_name=persona.name,
    )

    # ── Step 3: Call LLM ──────────────────────────────────────
    vision_kwargs = _prepare_vision_kwargs(creative)

    response = await call_anthropic(
        prompt=prompt,
        system=EVALUATOR_SYSTEM,
        model=config.eval_model,
        temperature=0.8,  # Higher temp for diverse, authentic reactions
        config=config,
        **vision_kwargs,
    )

    result = response.parse_json()

    # ── Step 4: Build evaluation ──────────────────────────────
    evaluation = PersonaEvaluation(
        evaluation_id=f"eval_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        creative_id=creative.creative_id,
        persona_id=persona.persona_id,
        primary_action=result["primary_action"],
        secondary_action=result.get("secondary_action"),
        sentiment=result["sentiment"],
        overall_score=result["overall_score"],
        attention_score=result["attention_score"],
        relevance_score=result["relevance_score"],
        trust_score=result["trust_score"],
        desire_score=result["desire_score"],
        clarity_score=result["clarity_score"],
        first_impression=result["first_impression"],
        reasoning=result["reasoning"],
        objections=result.get("objections", []),
        what_would_change_mind=result.get("what_would_change_mind"),
        verbatim_reaction=result["verbatim_reaction"],
        importance_score=result["importance_score"],
        category=creative.category,
        brand=creative.brand,
        key_themes=result.get("key_themes", []),
        model_used=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
        memories_retrieved=len(retrieved_memories),
        memory_context_used=memory_context if memory_context else None,
    )

    # ── Step 5: Store as memory ───────────────────────────────
    if memory_stream is not None:
        memory_stream.add_evaluation_memory(evaluation)

    return evaluation, response
