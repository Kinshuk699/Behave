"""
B2C Category Vocabulary & Brand Positioning — canonical constants.

All categories used in cohort selection, creative extraction, and persona
affinity matching MUST come from these lists. The LLM creative extraction
agent is constrained to pick from B2C_CATEGORIES, ensuring exact-match
cohort selection works reliably.
"""

from __future__ import annotations

from enum import Enum


# ── B2C Category Vocabulary ───────────────────────────────────

B2C_CATEGORIES: list[str] = [
    "electronics",
    "fashion",
    "food_and_beverage",
    "food_delivery",
    "quick_commerce",
    "skincare",
    "personal_care",
    "automobile",
    "two_wheeler",
    "home_services",
    "fintech",
    "edtech",
    "health_and_wellness",
    "travel",
    "telecom",
    "jewelry_and_luxury",
    "baby_and_kids",
    "grocery_and_household",
]

# ── Legacy → New Category Migration ──────────────────────────

CATEGORY_MIGRATION_MAP: dict[str, str] = {
    # Old free-text categories from past runs
    "Household": "grocery_and_household",
    "household": "grocery_and_household",
    "Maid Services": "home_services",
    "maid_services": "home_services",
    "maid services": "home_services",
    "grocery_delivery": "quick_commerce",
    "Grocery Delivery": "quick_commerce",
    "Automobile": "automobile",
    "House Maintenance": "home_services",
    "house_maintenance": "home_services",
    "house maintenance": "home_services",
    # Common user inputs that should normalize
    "househelp": "home_services",
    "cleaning": "home_services",
    "groceries": "grocery_and_household",
    "food": "food_and_beverage",
    "phones": "electronics",
    "mobile": "electronics",
    "clothing": "fashion",
    "clothes": "fashion",
    "beauty": "skincare",
    "cosmetics": "skincare",
    "cars": "automobile",
    "bikes": "two_wheeler",
    "scooters": "two_wheeler",
    "payments": "fintech",
    "upi": "fintech",
    "education": "edtech",
    "coaching": "edtech",
    "medicine": "health_and_wellness",
    "pharmacy": "health_and_wellness",
    "fitness": "health_and_wellness",
    "hotels": "travel",
    "flights": "travel",
    "sim": "telecom",
    "recharge": "telecom",
    "gold": "jewelry_and_luxury",
    "watches": "jewelry_and_luxury",
    "diapers": "baby_and_kids",
    "toys": "baby_and_kids",
}


def normalize_category(category: str) -> str:
    """Normalize a category string to canonical B2C vocabulary.

    1. Check if already in B2C_CATEGORIES (case-insensitive)
    2. Check migration map
    3. Fall back to lowercase original (for new categories from LLM extraction)
    """
    lower = category.lower().strip()

    # Direct match
    if lower in B2C_CATEGORIES:
        return lower

    # Migration map (try original case first, then lower)
    if category in CATEGORY_MIGRATION_MAP:
        return CATEGORY_MIGRATION_MAP[category]
    if lower in CATEGORY_MIGRATION_MAP:
        return CATEGORY_MIGRATION_MAP[lower]

    # Case-insensitive match against B2C list
    for cat in B2C_CATEGORIES:
        if cat.lower() == lower:
            return cat

    # No match — return lowered original
    return lower


def migrate_run_categories(runs_dir: "Path") -> int:
    """Migrate metadata.json files in runs_dir to use canonical categories.

    Returns the number of runs updated.
    """
    import json
    from pathlib import Path

    runs_dir = Path(runs_dir)
    updated = 0

    for meta_path in sorted(runs_dir.glob("*/metadata.json")):
        data = json.loads(meta_path.read_text())
        old_cat = data.get("category", "")
        new_cat = normalize_category(old_cat)
        if new_cat != old_cat:
            data["category"] = new_cat
            meta_path.write_text(json.dumps(data, indent=2, default=str))
            updated += 1

    return updated


# ── Brand Positioning Enums ───────────────────────────────────


class BrandPositioning(str, Enum):
    """How the brand positions itself in the market."""
    HERITAGE = "heritage"       # Coca-Cola, Cadbury, Tata
    PREMIUM = "premium"         # Apple, Samsung Galaxy S series
    MASS_MARKET = "mass_market" # Colgate, Parle-G, Maruti
    VALUE = "value"             # Xiaomi, D-Mart
    DISRUPTOR = "disruptor"     # Zepto, CRED, Ather
    LUXURY = "luxury"           # Louis Vuitton, Rolls Royce, Tanishq


class BrandEra(str, Enum):
    """How long the brand has been in consumers' lives."""
    LEGACY = "legacy"           # 50+ years — Tata, Amul, Coca-Cola
    ESTABLISHED = "established" # 10-50 years — Flipkart, Airtel
    GROWTH = "growth"           # 3-10 years — Zepto, CRED
    STARTUP = "startup"         # <3 years — new D2C brands


class MarketingTone(str, Enum):
    """The creative's communication style."""
    ASPIRATIONAL = "aspirational"     # "Be the best version"
    PLAYFUL = "playful"               # GenZ meme-style, witty
    INFORMATIONAL = "informational"   # Features, specs, comparisons
    URGENCY = "urgency"               # "Limited time", "Last few left"
    NOSTALGIA = "nostalgia"           # Childhood memories, heritage
    EDGY = "edgy"                     # Bold, provocative, boundary-pushing
