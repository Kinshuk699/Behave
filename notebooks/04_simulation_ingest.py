# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Simulation Ingest
# MAGIC
# MAGIC **Synthetic India — Agentic Creative Testing Platform**
# MAGIC
# MAGIC This notebook ingests real simulation run data through the full medallion pipeline:
# MAGIC 1. **Bronze**: Raw evaluations, scorecards, critic verdicts, and metadata
# MAGIC 2. **Silver**: Validated evaluations (reasoning >= 10 chars, verbatim >= 5 chars)
# MAGIC 3. **Gold**: Aggregated creative scorecards + run audit log
# MAGIC
# MAGIC **Usage**: Set `RUN_ID` to the simulation run you want to ingest.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

CATALOG = "bootcamp_students"
BRONZE = "kinshuk_bronze"
SILVER = "kinshuk_silver"
GOLD = "kinshuk_gold"

# Set to the run you want to ingest
RUN_ID = "run_e3d656cc826e"

# Bundle deployment path
BUNDLE_ROOT = "/Workspace/Users/kinshuk.sahni6@gmail.com/.bundle/Behave/dev/files"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Bronze — Ingest Raw Evaluations

# COMMAND ----------

import json, os
from datetime import datetime, timezone
from pyspark.sql import functions as F

run_dir = os.path.join(BUNDLE_ROOT, "data", "runs", RUN_ID)

# Load evaluations
eval_path = os.path.join(run_dir, "evaluations.json")
with open(eval_path) as f:
    raw_evals = json.load(f)

print(f"Loaded {len(raw_evals)} evaluations from {RUN_ID}")

# COMMAND ----------

# Load metadata
meta_path = os.path.join(run_dir, "metadata.json")
with open(meta_path) as f:
    metadata = json.load(f)

print(f"Run: {metadata['run_id']} | Brand: {metadata['brand']} | Category: {metadata['category']}")
print(f"Cost: ${metadata['total_cost_usd']:.4f} | Tokens: {metadata['total_tokens']}")

# COMMAND ----------

# Flatten evaluations for Delta — serialize list/dict fields as JSON strings
def _serialize(val):
    if isinstance(val, (list, dict)):
        return json.dumps(val, default=str)
    if val is None:
        return ""  # Spark can't infer type from None
    return val

eval_rows = []
for e in raw_evals:
    row = {k: _serialize(v) for k, v in e.items()}
    row["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    row["_run_id"] = RUN_ID
    eval_rows.append(row)

df_bronze_evals = spark.createDataFrame(eval_rows)
df_bronze_evals.write.mode("append").saveAsTable(f"{CATALOG}.{BRONZE}.evaluations")
print(f"✅ Wrote {len(eval_rows)} evaluations to {CATALOG}.{BRONZE}.evaluations")

# COMMAND ----------

# Load and ingest critic verdicts
critic_path = os.path.join(run_dir, "critic_verdicts.json")
if os.path.exists(critic_path):
    with open(critic_path) as f:
        raw_critics = json.load(f)

    critic_rows = []
    for c in raw_critics:
        row = {k: _serialize(v) for k, v in c.items()}
        row["_ingested_at"] = datetime.now(timezone.utc).isoformat()
        row["_run_id"] = RUN_ID
        critic_rows.append(row)

    df_bronze_critics = spark.createDataFrame(critic_rows)
    df_bronze_critics.write.mode("append").saveAsTable(f"{CATALOG}.{BRONZE}.critic_verdicts")
    print(f"✅ Wrote {len(critic_rows)} critic verdicts to {CATALOG}.{BRONZE}.critic_verdicts")
else:
    print("⚠️ No critic verdicts found — skipping")

# COMMAND ----------

# Ingest run metadata
meta_row = {k: _serialize(v) for k, v in metadata.items()}
meta_row["_ingested_at"] = datetime.now(timezone.utc).isoformat()

df_bronze_meta = spark.createDataFrame([meta_row])
df_bronze_meta.write.mode("append").saveAsTable(f"{CATALOG}.{BRONZE}.run_metadata")
print(f"✅ Wrote run metadata to {CATALOG}.{BRONZE}.run_metadata")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{BRONZE}.evaluations").filter(F.col("_run_id") == RUN_ID).select(
    "evaluation_id", "persona_id", "primary_action", "sentiment", "overall_score", "cost_usd"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Silver — Validate Evaluations

# COMMAND ----------

# Read bronze evaluations for this run
df_bronze = spark.table(f"{CATALOG}.{BRONZE}.evaluations").filter(F.col("_run_id") == RUN_ID)
bronze_rows = [row.asDict() for row in df_bronze.collect()]
print(f"Bronze evaluations for {RUN_ID}: {len(bronze_rows)}")

# COMMAND ----------

# Apply validation rules
now = datetime.now(timezone.utc).isoformat()

passed_rows = []
quarantined_rows = []

for row in bronze_rows:
    errors = []

    if not row.get("evaluation_id"):
        errors.append("missing evaluation_id")

    reasoning = row.get("reasoning", "")
    if not reasoning or len(str(reasoning)) < 10:
        errors.append("reasoning too short")

    verbatim = row.get("verbatim_reaction", "")
    if not verbatim or len(str(verbatim)) < 5:
        errors.append("verbatim_reaction too short")

    if errors:
        quarantined_rows.append({
            "record_id": row.get("evaluation_id", "unknown"),
            "source_table": "evaluations",
            "errors": "; ".join(errors),
            "_quarantined_at": now,
        })
    else:
        row_copy = dict(row)
        row_copy["_validated_at"] = now
        passed_rows.append(row_copy)

print(f"✅ Evaluations — Passed: {len(passed_rows)}/{len(bronze_rows)} | Quarantined: {len(quarantined_rows)}/{len(bronze_rows)}")

# COMMAND ----------

# Write validated evaluations to silver
if passed_rows:
    df_silver_evals = spark.createDataFrame(passed_rows)
    df_silver_evals.write.mode("append").saveAsTable(f"{CATALOG}.{SILVER}.evaluations")
    print(f"✅ Wrote {len(passed_rows)} validated evaluations to {CATALOG}.{SILVER}.evaluations")

# Write quarantine records (if any)
if quarantined_rows:
    df_quarantine = spark.createDataFrame(quarantined_rows)
    df_quarantine.write.mode("append").saveAsTable(f"{CATALOG}.{SILVER}.quarantine")
    print(f"⚠️ Wrote {len(quarantined_rows)} quarantined records")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{SILVER}.evaluations").filter(F.col("_run_id") == RUN_ID).select(
    "evaluation_id", "persona_id", "primary_action", "overall_score", "reasoning", "_validated_at"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Gold — Aggregate Scorecards

# COMMAND ----------

# Read silver evaluations for this run
df_silver = spark.table(f"{CATALOG}.{SILVER}.evaluations").filter(F.col("_run_id") == RUN_ID)
silver_rows = [row.asDict() for row in df_silver.collect()]
print(f"Silver evaluations for scorecard: {len(silver_rows)}")

# COMMAND ----------

from collections import Counter

# Group by creative_id
creative_groups = {}
for row in silver_rows:
    cid = row.get("creative_id", "unknown")
    creative_groups.setdefault(cid, []).append(row)

scorecard_rows = []
for creative_id, evals in creative_groups.items():
    n = len(evals)
    actions = Counter(r.get("primary_action", "unknown") for r in evals)
    sentiments = Counter(r.get("sentiment", "unknown") for r in evals)

    avg = lambda key: round(sum(float(r.get(key, 0) or 0) for r in evals) / n, 2)

    scorecard_rows.append({
        "run_id": RUN_ID,
        "creative_id": creative_id,
        "brand": evals[0].get("brand", ""),
        "category": evals[0].get("category", ""),
        "n_personas_evaluated": n,
        "avg_overall_score": avg("overall_score"),
        "avg_attention": avg("attention_score"),
        "avg_relevance": avg("relevance_score"),
        "avg_trust": avg("trust_score"),
        "avg_desire": avg("desire_score"),
        "avg_clarity": avg("clarity_score"),
        "action_distribution": json.dumps(dict(actions)),
        "sentiment_distribution": json.dumps(dict(sentiments)),
        "status": "completed",
        "_materialized_at": datetime.now(timezone.utc).isoformat(),
    })

print(f"Built {len(scorecard_rows)} scorecards")

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

scorecard_schema = StructType([
    StructField("run_id", StringType(), True),
    StructField("creative_id", StringType(), True),
    StructField("brand", StringType(), True),
    StructField("category", StringType(), True),
    StructField("n_personas_evaluated", IntegerType(), True),
    StructField("avg_overall_score", DoubleType(), True),
    StructField("avg_attention", DoubleType(), True),
    StructField("avg_relevance", DoubleType(), True),
    StructField("avg_trust", DoubleType(), True),
    StructField("avg_desire", DoubleType(), True),
    StructField("avg_clarity", DoubleType(), True),
    StructField("action_distribution", StringType(), True),
    StructField("sentiment_distribution", StringType(), True),
    StructField("status", StringType(), True),
    StructField("_materialized_at", StringType(), True),
])

df_gold_scorecards = spark.createDataFrame(scorecard_rows, schema=scorecard_schema)
df_gold_scorecards.write.mode("append").saveAsTable(f"{CATALOG}.{GOLD}.creative_scorecards")
print(f"✅ Wrote {len(scorecard_rows)} scorecards to {CATALOG}.{GOLD}.creative_scorecards")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{GOLD}.creative_scorecards").filter(F.col("run_id") == RUN_ID))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Run Audit Log

# COMMAND ----------

audit_row = {
    "run_id": RUN_ID,
    "brand": metadata.get("brand", ""),
    "category": metadata.get("category", ""),
    "n_creatives": len(creative_groups),
    "n_personas_ingested": metadata.get("total_evaluations", 0),
    "total_evaluations": metadata.get("total_evaluations", 0),
    "successful_evaluations": metadata.get("successful_evaluations", 0),
    "quarantined_records": len(quarantined_rows),
    "pipeline_stage": "simulation_ingest",
    "status": "completed",
    "_materialized_at": datetime.now(timezone.utc).isoformat(),
}

df_audit = spark.createDataFrame([audit_row])
df_audit.write.mode("append").saveAsTable(f"{CATALOG}.{GOLD}.run_audit_log")
print(f"✅ Wrote audit log entry for {RUN_ID}")

# COMMAND ----------

display(spark.table(f"{CATALOG}.{GOLD}.run_audit_log").filter(F.col("run_id") == RUN_ID))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. MLflow Experiment Tracking

# COMMAND ----------

import mlflow

experiment_path = "/Users/kinshuk.sahni6@gmail.com/synthetic_india"
mlflow.set_experiment(experiment_path)

# Build scorecard summary from gold table
gold_scorecards = spark.table(f"{CATALOG}.{GOLD}.creative_scorecards").filter(F.col("run_id") == RUN_ID).toPandas()

avg_overall = float(gold_scorecards["avg_overall_score"].mean()) if len(gold_scorecards) else 0.0

with mlflow.start_run(run_name=RUN_ID):
    # Log params
    mlflow.log_params({
        "run_id": RUN_ID,
        "brand": metadata.get("brand", ""),
        "category": metadata.get("category", ""),
        "cohort_size": str(metadata.get("cohort_size", "")),
    })

    # Log metrics
    mlflow.log_metrics({
        "avg_overall_score": avg_overall,
        "total_cost_usd": float(metadata.get("total_cost_usd", 0.0)),
        "total_tokens": int(metadata.get("total_tokens", 0)),
        "n_personas_evaluated": len(gold_scorecards),
        "quarantine_rate": len(quarantined_rows) / max(len(raw_evals), 1),
    })

    # Log raw run data as artifacts
    mlflow.log_artifact(os.path.join(run_dir, "evaluations.json"))
    mlflow.log_artifact(os.path.join(run_dir, "recommendation.json"))

print(f"✅ Logged MLflow run for {RUN_ID} under experiment {experiment_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline Summary
# MAGIC
# MAGIC | Layer | Table | Operation | Status |
# MAGIC |-------|-------|-----------|--------|
# MAGIC | Bronze | `evaluations` | Append raw evals | ✅ |
# MAGIC | Bronze | `critic_verdicts` | Append critic data | ✅ |
# MAGIC | Bronze | `run_metadata` | Append run info | ✅ |
# MAGIC | Silver | `evaluations` | Validated evals | ✅ |
# MAGIC | Silver | `quarantine` | Bad records | ✅ |
# MAGIC | Gold | `creative_scorecards` | Aggregated scores | ✅ |
# MAGIC | Gold | `run_audit_log` | Audit trail | ✅ |
# MAGIC | MLflow | experiment | Params + metrics | ✅ |
# MAGIC
# MAGIC **Note**: This notebook uses `mode("append")` — safe to re-run for different `RUN_ID` values.
# MAGIC Use Delta time travel if you need to deduplicate.
