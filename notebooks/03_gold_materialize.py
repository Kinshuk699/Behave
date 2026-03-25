# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Gold Materialization
# MAGIC
# MAGIC **Synthetic India — Agentic Creative Testing Platform**
# MAGIC
# MAGIC This notebook aggregates silver data into gold analytics tables:
# MAGIC - `creative_scorecards` — per-creative aggregate metrics + grade
# MAGIC - `run_audit_log` — pipeline run metadata + quality stats
# MAGIC
# MAGIC Gold tables are **analytics-ready** and feed the dashboard.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

CATALOG = "bootcamp_students"
SILVER = "kinshuk_silver"
GOLD = "kinshuk_gold"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Creative Scorecards
# MAGIC
# MAGIC Aggregates validated persona evaluations by `(run_id, creative_id)` into:
# MAGIC - Average dimensional scores (attention, relevance, trust, desire, clarity)
# MAGIC - Action & sentiment distributions
# MAGIC - Grade assignment
# MAGIC
# MAGIC **Note:** This table will be populated after a simulation run produces
# MAGIC evaluation data. For now, we create a placeholder scorecard from the
# MAGIC available silver data to demonstrate the pipeline.

# COMMAND ----------

import json
from datetime import datetime, timezone
from pyspark.sql import functions as F

# Build a demo scorecard from silver personas + creatives
# (Real scorecards come from gold_persona_evaluations after a simulation run)

df_personas = spark.table(f"{CATALOG}.{SILVER}.personas")
df_creatives = spark.table(f"{CATALOG}.{SILVER}.creative_cards")

n_personas = df_personas.count()
n_creatives = df_creatives.count()

print(f"Silver data: {n_personas} personas, {n_creatives} creatives")

# COMMAND ----------

# Build scorecard rows — one per creative, showing ready-state
scorecard_rows = []
creative_rows = df_creatives.collect()

for row in creative_rows:
    scorecard = {
        "run_id": "pre_simulation",
        "creative_id": row["creative_id"],
        "brand": row["brand"],
        "category": row.get("category", "skincare"),
        "n_personas_available": n_personas,
        "n_personas_evaluated": 0,  # Pre-simulation
        "avg_overall_score": None,
        "avg_attention": None,
        "avg_relevance": None,
        "avg_trust": None,
        "avg_desire": None,
        "avg_clarity": None,
        "action_distribution": "{}",
        "sentiment_distribution": "{}",
        "status": "awaiting_simulation",
        "_materialized_at": datetime.now(timezone.utc).isoformat(),
    }
    scorecard_rows.append(scorecard)

df_scorecards = spark.createDataFrame(scorecard_rows)
df_scorecards.write.mode("overwrite").saveAsTable(f"{CATALOG}.{GOLD}.creative_scorecards")
print(f"✅ Wrote {len(scorecard_rows)} scorecard rows to {CATALOG}.{GOLD}.creative_scorecards")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{GOLD}.creative_scorecards"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Run Audit Log

# COMMAND ----------

# Build audit row for this pipeline run
audit_row = {
    "run_id": "pipeline_init",
    "brand": "Synthetic India",
    "category": "skincare",
    "n_creatives": n_creatives,
    "n_personas_ingested": n_personas,
    "total_evaluations": 0,
    "successful_evaluations": 0,
    "quarantined_records": 0,
    "pipeline_stage": "bronze_silver_gold_init",
    "status": "completed",
    "_materialized_at": datetime.now(timezone.utc).isoformat(),
}

df_audit = spark.createDataFrame([audit_row])
df_audit.write.mode("overwrite").saveAsTable(f"{CATALOG}.{GOLD}.run_audit_log")
print(f"✅ Wrote audit log to {CATALOG}.{GOLD}.run_audit_log")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{GOLD}.run_audit_log"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Pipeline Summary
# MAGIC
# MAGIC ### Tables Created
# MAGIC
# MAGIC | Layer | Table | Rows | Status |
# MAGIC |-------|-------|------|--------|
# MAGIC | Bronze | `kinshuk_bronze.persona_seed` | 20 | ✅ Ingested |
# MAGIC | Bronze | `kinshuk_bronze.creative_uploads` | 3 | ✅ Ingested |
# MAGIC | Silver | `kinshuk_silver.personas` | 20 | ✅ Validated |
# MAGIC | Silver | `kinshuk_silver.creative_cards` | 3 | ✅ Validated |
# MAGIC | Silver | `kinshuk_silver.quarantine` | 0 | ✅ Clean |
# MAGIC | Gold | `kinshuk_gold.creative_scorecards` | 3 | ✅ Awaiting simulation |
# MAGIC | Gold | `kinshuk_gold.run_audit_log` | 1 | ✅ Pipeline init |

# COMMAND ----------

# Final verification — query all tables
for schema, table in [
    (f"{CATALOG}.kinshuk_bronze", "persona_seed"),
    (f"{CATALOG}.kinshuk_bronze", "creative_uploads"),
    (f"{CATALOG}.kinshuk_silver", "personas"),
    (f"{CATALOG}.kinshuk_silver", "creative_cards"),
    (f"{CATALOG}.kinshuk_gold", "creative_scorecards"),
    (f"{CATALOG}.kinshuk_gold", "run_audit_log"),
]:
    count = spark.table(f"{schema}.{table}").count()
    print(f"  {schema}.{table}: {count} rows")

print("\n🎉 Medallion pipeline initialized successfully!")
