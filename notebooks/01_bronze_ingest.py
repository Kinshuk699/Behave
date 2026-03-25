# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingestion
# MAGIC
# MAGIC **Synthetic India — Agentic Creative Testing Platform**
# MAGIC
# MAGIC This notebook ingests raw data into the bronze layer:
# MAGIC - `persona_seed` — 20 consumer personas from JSON library
# MAGIC - `creative_uploads` — demo creatives (Minimalist, Dot & Key, Mamaearth)
# MAGIC
# MAGIC Bronze is **append-only and immutable**. No transformations, no cleaning.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

CATALOG = "bootcamp_students"
SCHEMA = "kinshuk_bronze"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Ingest Persona Seeds

# COMMAND ----------

import json, os

# Read all persona JSON files from the deployed bundle
# When deployed via `databricks bundle deploy`, files land at:
# /Workspace/Users/<email>/.bundle/<bundle_name>/dev/files/
persona_dir = os.path.join(
    "/Workspace/Users/kinshuk.sahni6@gmail.com/.bundle/Behave/dev/files",
    "data", "personas"
)

persona_rows = []
for fname in sorted(os.listdir(persona_dir)):
    if fname.endswith(".json"):
        with open(os.path.join(persona_dir, fname)) as f:
            raw = json.load(f)

        # Flatten nested fields for columnar storage
        flat = {
            "persona_id": raw.get("persona_id"),
            "name": raw.get("name"),
            "archetype": raw.get("archetype"),
            "tagline": raw.get("tagline"),
            "backstory": raw.get("backstory"),
            "current_life_context": raw.get("current_life_context"),
            "inner_monologue_style": raw.get("inner_monologue_style"),
        }

        # Demographics
        demo = raw.get("demographics", {})
        for key in ("age", "gender", "city", "city_tier", "income_segment",
                     "education", "occupation", "family_status"):
            flat[key] = demo.get(key)

        # Purchase psychology
        psych = raw.get("purchase_psychology", {})
        for key in ("price_sensitivity", "brand_loyalty", "impulse_tendency",
                     "social_proof_need", "research_depth", "risk_tolerance",
                     "decision_speed", "deal_sensitivity"):
            flat[key] = psych.get(key)

        # Media behavior
        media = raw.get("media_behavior", {})
        for key in ("platform_primary", "ad_tolerance", "scroll_speed",
                     "video_preference", "influencer_trust"):
            flat[key] = media.get(key)
        flat["content_language_preference"] = media.get("content_language_preference")

        # Serialize complex nested fields as JSON strings
        flat["category_affinities"] = json.dumps(raw.get("category_affinities", []))
        flat["emotional_profile"] = json.dumps(raw.get("emotional_profile", {}))

        persona_rows.append(flat)

print(f"Loaded {len(persona_rows)} personas")

# COMMAND ----------

from pyspark.sql import functions as F
from datetime import datetime, timezone

df_personas = spark.createDataFrame(persona_rows)
df_personas = df_personas.withColumn("_ingested_at", F.lit(datetime.now(timezone.utc).isoformat()))

df_personas.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.persona_seed")
print(f"✅ Wrote {df_personas.count()} rows to {CATALOG}.{SCHEMA}.persona_seed")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{SCHEMA}.persona_seed").select(
    "persona_id", "name", "archetype", "city", "city_tier", "_ingested_at"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Ingest Demo Creatives

# COMMAND ----------

# Demo creatives — same as build_demo_creatives() in cli.py
creative_rows = [
    {
        "creative_id": "demo_creative_01",
        "brand": "Minimalist",
        "category": "skincare",
        "format": "static_image",
        "headline": "10% Niacinamide Face Serum",
        "body_copy": "Targets blemishes, uneven skin tone and signs of ageing. Dermatologist tested. No added fragrance.",
        "cta_text": "Shop Now",
        "cta_type": "shop",
        "price_shown": 599.0,
        "original_price": 649.0,
        "discount_percentage": 7.7,
        "price_framing": "value",
        "urgency_cues": json.dumps(["Limited time offer"]),
        "social_proof_cues": json.dumps(["10L+ units sold", "4.2★ (45K ratings)"]),
        "trust_signals": json.dumps(["Dermatologist tested", "No added fragrance", "FSA approved"]),
        "emotional_hooks": json.dumps(["Clear skin confidence"]),
        "visual_style": "minimal",
        "product_visibility": 0.9,
        "human_presence": False,
        "celebrity_present": False,
        "language_primary": "English",
        "code_mixed": False,
        "extraction_confidence": 0.92,
    },
    {
        "creative_id": "demo_creative_02",
        "brand": "Dot & Key",
        "category": "skincare",
        "format": "carousel",
        "headline": "Vitamin C + E Super Bright Serum",
        "body_copy": "Get that lit-from-within glow! 20X Vitamin C power. Goes on like a dream, works while you slay.",
        "cta_text": "Add to Bag",
        "cta_type": "add_to_cart",
        "price_shown": 695.0,
        "original_price": 845.0,
        "discount_percentage": 17.8,
        "price_framing": "discount",
        "urgency_cues": json.dumps(["Bestseller", "Selling fast"]),
        "social_proof_cues": json.dumps(["Nykaa bestseller", "Featured on Shark Tank India"]),
        "trust_signals": json.dumps(["Cruelty-free", "Paraben-free"]),
        "emotional_hooks": json.dumps(["Glow up", "Slay every day"]),
        "visual_style": "bold_graphic",
        "product_visibility": 0.85,
        "human_presence": True,
        "celebrity_present": False,
        "language_primary": "English",
        "code_mixed": True,
        "extraction_confidence": 0.88,
    },
    {
        "creative_id": "demo_creative_03",
        "brand": "Mamaearth",
        "category": "skincare",
        "format": "static_image",
        "headline": "Ubtan Face Wash — Diwali Glow Special",
        "body_copy": "Tyohaar ki taiyyari ho ya roz ka skincare, haldi aur kesar ka jaadu ab daily. Paraben-free, toxin-free.",
        "cta_text": "Shop Diwali Offer",
        "cta_type": "shop",
        "price_shown": 349.0,
        "original_price": 449.0,
        "discount_percentage": 22.3,
        "price_framing": "discount",
        "urgency_cues": json.dumps(["Diwali special", "Limited edition pack"]),
        "social_proof_cues": json.dumps(["5M+ happy customers", "India's #1 toxin-free brand"]),
        "trust_signals": json.dumps(["Made Safe certified", "Dermatologically tested", "Toxin-free"]),
        "emotional_hooks": json.dumps(["Festival glow", "Natural beauty", "Family tradition"]),
        "visual_style": "traditional",
        "product_visibility": 0.8,
        "human_presence": True,
        "celebrity_present": False,
        "language_primary": "Hindi",
        "language_secondary": "English",
        "code_mixed": True,
        "festival_context": "Diwali",
        "target_city_tier": "Pan-India",
        "cultural_references": json.dumps(["haldi (turmeric)", "diyas", "rangoli motifs"]),
        "extraction_confidence": 0.90,
    },
]

print(f"Prepared {len(creative_rows)} demo creatives")

# COMMAND ----------

df_creatives = spark.createDataFrame(creative_rows)
df_creatives = df_creatives.withColumn("_ingested_at", F.lit(datetime.now(timezone.utc).isoformat()))

df_creatives.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.creative_uploads")
print(f"✅ Wrote {df_creatives.count()} rows to {CATALOG}.{SCHEMA}.creative_uploads")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{SCHEMA}.creative_uploads").select(
    "creative_id", "brand", "headline", "price_shown", "format", "_ingested_at"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC Bronze ingestion complete:
# MAGIC - `persona_seed`: 20 consumer personas (8 archetypes, 10 cities)
# MAGIC - `creative_uploads`: 3 demo creatives (Minimalist, Dot & Key, Mamaearth Diwali)
# MAGIC
# MAGIC Next: Run `02_silver_transform` to validate and clean.
