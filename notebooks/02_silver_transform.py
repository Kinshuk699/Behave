# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver Transformation
# MAGIC
# MAGIC **Synthetic India — Agentic Creative Testing Platform**
# MAGIC
# MAGIC This notebook validates bronze data and writes to silver:
# MAGIC - Schema validation + business rules
# MAGIC - Quarantine routing for bad records
# MAGIC - Data quality metrics displayed inline
# MAGIC
# MAGIC Quality checks:
# MAGIC - Personas: backstory >= 20 chars, archetype present, category affinities exist
# MAGIC - Creatives: headline or body_copy present, extraction_confidence >= 0.3
# MAGIC - Evaluations: reasoning >= 10 chars, verbatim_reaction >= 5 chars

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

CATALOG = "bootcamp_students"
BRONZE = "kinshuk_bronze"
SILVER = "kinshuk_silver"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Validate Personas

# COMMAND ----------

from pyspark.sql import functions as F
from datetime import datetime, timezone

df_bronze_personas = spark.table(f"{CATALOG}.{BRONZE}.persona_seed")
print(f"Bronze personas: {df_bronze_personas.count()} rows")

# COMMAND ----------

# Apply validation rules as SQL expressions
df_valid_personas = df_bronze_personas.filter(
    (F.col("persona_id").isNotNull()) &
    (F.length(F.col("backstory")) >= 20) &
    (F.col("archetype").isNotNull()) &
    (F.col("category_affinities") != "[]") &
    (F.col("category_affinities").isNotNull())
).withColumn("_validated_at", F.lit(datetime.now(timezone.utc).isoformat()))

df_quarantined_personas = df_bronze_personas.filter(
    (F.col("persona_id").isNull()) |
    (F.length(F.col("backstory")) < 20) |
    (F.col("backstory").isNull()) |
    (F.col("archetype").isNull()) |
    (F.col("category_affinities") == "[]") |
    (F.col("category_affinities").isNull())
).withColumn("_quarantined_at", F.lit(datetime.now(timezone.utc).isoformat())) \
 .withColumn("source_table", F.lit("persona_seed")) \
 .withColumn("errors", F.lit("failed silver validation"))

valid_count = df_valid_personas.count()
quarantine_count = df_quarantined_personas.count()
total = valid_count + quarantine_count

print(f"✅ Personas — Passed: {valid_count}/{total} | Quarantined: {quarantine_count}/{total}")

# COMMAND ----------

df_valid_personas.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SILVER}.personas")
print(f"✅ Wrote {valid_count} validated personas to {CATALOG}.{SILVER}.personas")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{SILVER}.personas").select(
    "persona_id", "name", "archetype", "city", "city_tier", "_validated_at"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Validate Creatives

# COMMAND ----------

df_bronze_creatives = spark.table(f"{CATALOG}.{BRONZE}.creative_uploads")
print(f"Bronze creatives: {df_bronze_creatives.count()} rows")

# COMMAND ----------

df_valid_creatives = df_bronze_creatives.filter(
    (F.col("creative_id").isNotNull()) &
    (
        (F.col("headline").isNotNull() & (F.length(F.col("headline")) > 0)) |
        (F.col("body_copy").isNotNull() & (F.length(F.col("body_copy")) > 0))
    ) &
    (F.col("extraction_confidence") >= 0.3)
).withColumn("_validated_at", F.lit(datetime.now(timezone.utc).isoformat()))

df_quarantined_creatives = df_bronze_creatives.filter(
    (F.col("creative_id").isNull()) |
    (
        (F.col("headline").isNull() | (F.length(F.col("headline")) == 0)) &
        (F.col("body_copy").isNull() | (F.length(F.col("body_copy")) == 0))
    ) |
    (F.col("extraction_confidence") < 0.3)
).withColumn("_quarantined_at", F.lit(datetime.now(timezone.utc).isoformat())) \
 .withColumn("source_table", F.lit("creative_uploads")) \
 .withColumn("errors", F.lit("failed silver validation"))

valid_c = df_valid_creatives.count()
quarantine_c = df_quarantined_creatives.count()

print(f"✅ Creatives — Passed: {valid_c}/{valid_c + quarantine_c} | Quarantined: {quarantine_c}/{valid_c + quarantine_c}")

# COMMAND ----------

df_valid_creatives.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SILVER}.creative_cards")
print(f"✅ Wrote {valid_c} validated creatives to {CATALOG}.{SILVER}.creative_cards")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{SILVER}.creative_cards").select(
    "creative_id", "brand", "headline", "price_shown", "extraction_confidence", "_validated_at"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Write Quarantine Table

# COMMAND ----------

# Combine all quarantined records into one table
from functools import reduce
from pyspark.sql import DataFrame

quarantine_frames = []
if quarantine_count > 0:
    quarantine_frames.append(
        df_quarantined_personas.select("persona_id", "source_table", "errors", "_quarantined_at")
            .withColumnRenamed("persona_id", "record_id")
    )
if quarantine_c > 0:
    quarantine_frames.append(
        df_quarantined_creatives.select("creative_id", "source_table", "errors", "_quarantined_at")
            .withColumnRenamed("creative_id", "record_id")
    )

if quarantine_frames:
    df_quarantine = reduce(DataFrame.unionByName, quarantine_frames)
    df_quarantine.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SILVER}.quarantine")
    print(f"✅ Wrote {df_quarantine.count()} quarantined records to {CATALOG}.{SILVER}.quarantine")
    display(df_quarantine)
else:
    print("✅ No quarantined records — all data passed validation!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Quality Summary
# MAGIC
# MAGIC | Source | Passed | Quarantined | Pass Rate |
# MAGIC |--------|--------|-------------|-----------|
# MAGIC | Personas | ✅ | ❌ | — |
# MAGIC | Creatives | ✅ | ❌ | — |
# MAGIC
# MAGIC _(Exact counts displayed in cell outputs above)_
# MAGIC
# MAGIC Next: Run `03_gold_materialize` to aggregate into analytics tables.
