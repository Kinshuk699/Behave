# Roadmap — What's Next

**Last updated:** 2025-03-25

## Completed ✅

| # | Feature | Date | Tests |
|---|---|---|---|
| 1 | Fix CLI output — print_run_header + print_run_summary | 2025-03-25 | 8/8 GREEN |
| 2 | Critic Agent — quality gate with 4 dimensions | 2025-03-25 | 16/16 GREEN |
| 3 | Vision-Native Evaluation — image_path + base64 + vision API | 2025-03-25 | 21/21 GREEN |
| 4 | Trend Follower Persona — Priya Malhotra, Delhi, FOMO archetype | 2025-03-25 | 23/23 GREEN |
| 5 | Full-Dump Memory Mode + MemoryConsumer — category-scoped, cross-reflection toggle | 2025-03-25 | 31/31 GREEN |

## Up Next (in order)

### 6. Tiered Model Support
Haiku/4o-mini for volume evals, Sonnet for **Critic Agent**.
- Currently everything runs on Sonnet (expensive)
- Cost target: ~₹100 per 20-persona run
- **Why:** Makes real-world testing affordable

### 7. Tune CreativeCard for Indian Ads
Test **Creative Analysis** with real Hinglish copy, ₹ pricing, cultural refs.

### 8. Expand Persona Library to 20+
3-5 personas per archetype, varying demographics/city/language.

### 9. Port to Databricks
**Medallion Pipeline** as Delta tables. Capstone phase.
- Bronze → append-only Delta tables
- Silver → DLT expectations (schema + **Critic** quality)
- Gold → Unity Catalog analytics views


