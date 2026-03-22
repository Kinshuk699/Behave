"""
Cohort Selection — choose which personas evaluate a given creative.

The spec is clear: bad persona selection can make the whole simulation
look inaccurate even if individual agent prompts are good. This module
handles matching personas to creatives based on category affinity,
demographic relevance, and archetype diversity.
"""

from __future__ import annotations

from typing import Optional

from synthetic_india.schemas.persona import PersonaProfile


def select_cohort(
    personas: list[PersonaProfile],
    category: str,
    cohort_size: int = 20,
    required_archetypes: Optional[list[str]] = None,
) -> list[PersonaProfile]:
    """
    Select a cohort of personas for evaluating a creative.

    Strategy:
    1. Prioritize personas with category affinity
    2. Ensure archetype diversity
    3. Fill remaining slots with demographic diversity

    Args:
        personas: Full persona library
        category: Product category being evaluated
        cohort_size: Target cohort size
        required_archetypes: Archetypes that must be included
    """
    if len(personas) <= cohort_size:
        return personas

    scored: list[tuple[float, PersonaProfile]] = []

    for persona in personas:
        score = 0.0

        # Category affinity
        for aff in persona.category_affinities:
            if aff.category.lower() == category.lower():
                score += aff.interest_level * 5.0
                break
        else:
            # No explicit affinity — slight penalty
            score += 0.5

        # Behavioral archetype diversity bonus
        if required_archetypes and persona.archetype in required_archetypes:
            score += 3.0

        scored.append((score, persona))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    selected: list[PersonaProfile] = []
    selected_archetypes: set[str] = set()

    # First pass: ensure archetype diversity
    if required_archetypes:
        for archetype in required_archetypes:
            for score, persona in scored:
                if persona.archetype == archetype and persona not in selected:
                    selected.append(persona)
                    selected_archetypes.add(persona.archetype)
                    break

    # Second pass: fill remaining slots by score
    for score, persona in scored:
        if len(selected) >= cohort_size:
            break
        if persona not in selected:
            selected.append(persona)
            selected_archetypes.add(persona.archetype)

    return selected
