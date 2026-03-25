# Synthetic India Capstone Roadmap

Last updated: 2026-03-25 (aligned with synthetic_india_v2.docx)

## 1. Final framing

Project title:

Synthetic India: An Agentic Creative Testing Platform for Indian D2C Brands

One-line pitch:

Synthetic India is a Databricks-native, multi-source consumer simulation and recommendation engine that helps brands reduce creative testing risk before ad spend by evaluating creatives against calibrated Indian consumer personas and producing actionable recommendations.

## 2. What the capstone is really proving

This project should prove five things clearly:

1. There is a real cloud data pipeline.
2. The pipeline has visible data quality controls.
3. The project uses multiple data inputs in a meaningful joined model.
4. An agent takes an action beyond summarization.
5. The final output is business-valuable and demoable.

## 3. The right scope

Do not build the full persistent generative-agents-style society for the capstone.

Build the strongest finishable version:

- stateless or lightly stateful persona evaluation
- visible Databricks medallion pipeline
- high-quality persona library
- structured creative extraction
- scoring + recommendation engine
- one agent that decides what to do next

This keeps the Generative Agents inspiration while fitting the course rubric.

## 4. How Generative Agents still influences this project

Keep these ideas from the paper/repo:

- agents should be grounded in rich persona state, not shallow demographics
- evaluation should use relevant context, not a single prompt blob
- outputs should be structured enough to become part of the system state
- future extensibility for memory and agent-to-agent influence should remain possible

v2 additions from 2026 tech:

- vision-native evaluation: raw ad image goes to each persona alongside CreativeCard
- full dump memory mode: 200K context windows mean we skip retrieval for Phase 1-2
- structured output enforced at API level via Pydantic schemas
- Critic Agent: quality gate checking persona consistency, sycophancy, cultural authenticity
- cheaper inference: Haiku/4o-mini for volume evals, premium models for Critic + reports

Do not try to implement for capstone:

- long-horizon memory retrieval (full dump mode is sufficient)
- social world simulation
- persistent daily plans
- agent-to-agent conversations
- all 10 India-specific use cases (pick 1-2 for demo)

For the capstone, use the paper as conceptual inspiration, not as the literal implementation target.

## 5. Recommended system architecture

### 5.1 Data sources

Use at least three source families.

Source A: Creative inputs
- ad images
- landing page screenshots
- copy/headline/body/CTA text
- optional competitor creatives

Source B: Persona inputs
- curated consumer persona library
- demographic fields
- behavioral archetype fields
- category affinity fields
- price sensitivity / trust / decision speed / social proof preferences

Source C: Market context inputs
- category benchmark table
- price bands
- trend tags
- seasonal context
- brand/category metadata

Optional Source D: Calibration / feedback inputs
- actual campaign outcomes
- human evaluation labels
- scaled creative choice

### 5.2 Medallion design

Bronze
- raw creative uploads metadata
- raw extracted creative text/vision outputs
- raw persona seed records
- raw category benchmark/context records
- raw run request metadata

Silver
- cleaned creative cards
- validated persona profiles
- normalized category benchmark tables
- enriched run cohort table
- creative-to-persona evaluation input table
- quarantined bad records table

Gold
- persona evaluation results
- segment-level creative summaries
- creative scorecards
- recommendation outputs
- agent decision logs
- dashboard-ready business metrics

## 6. Databricks implementation choice

Primary choice:

- Databricks Delta tables
- Delta Live Tables if available
- batch or triggered micro-batch execution
- MLflow for evaluation and tracing
- Databricks SQL dashboard for demo

Recommendation:

Use triggered batch or micro-batch, not always-on streaming.

Reason:

- better aligned with actual creative testing workflow
- cheaper
- simpler to debug
- still demonstrates pipeline engineering

Optional enhancement:

- Auto Loader watches an upload path for new creative assets
- each new submission triggers a new evaluation run

## 7. Data quality requirements

Make data quality visible in the demo.

Must-have checks:

- required creative fields present
- CTA extracted or explicitly null-labeled
- category values in allowed set
- price parsing valid if present
- persona schema valid and complete
- duplicate creative submissions detected
- invalid records routed to quarantine table

If using DLT:

- use expectations and drop/fail/quarantine logic visibly

If not using DLT:

- create explicit assertion tables and bad-record outputs

## 8. Agent design

### 8.1 What the agents must do

Two agent roles (v2):

**Critic Agent** (quality gate — new in v2):
- reviews each persona evaluation before it enters the pipeline
- checks: persona consistency, sycophancy detection, cultural authenticity, action-reasoning alignment
- outputs: PASS or FAIL with specific issues
- FAIL → re-run or routed to quarantine

**Recommendation Agent** (business action):
- takes one concrete business action
- recommended action: choose which creative to scale and why
- additional supported actions:
  - flag high-risk creatives likely to trigger negative sentiment
  - generate prioritized edit recommendations
  - recommend which audience segment to target first

### 8.2 Agent inputs

- creative scorecard from gold layer
- segment-level reaction summaries
- top persona verbatims
- benchmark context
- optional competitor comparison

### 8.3 Agent outputs

Structured output table, for example:

- `run_id`
- `winning_creative_id`
- `recommended_action`
- `reasoning_summary`
- `top_risks`
- `top_edits`
- `confidence_score`
- `created_at`

### 8.4 Agent logging

Log all of these:

- prompt input references or tool input payloads
- model used
- run metadata
- final recommendation
- token usage / cost
- failure state if output is invalid

This is part of what makes the project feel production-minded.

## 9. Demo flow

The final demo should be extremely clean.

Recommended narrative:

1. Upload or register two or three creatives.
2. Show bronze ingestion in Databricks.
3. Show creative-card extraction and persona/context joins in silver.
4. Show evaluation outputs and aggregate scoring in gold.
5. Show data quality checks and one quarantined example.
6. Show the agent recommendation.
7. Show the dashboard that explains which creative to scale and what to change.

Business framing during demo:

This reduces creative testing risk before ad spend by simulating likely audience response across multiple consumer archetypes and turning the results into action.

## 10. Roadmap by step

### Step 1. Lock the capstone scope

Goal:

- freeze the project as creative testing + recommendation, not full social simulation

Deliverable:

- final project definition and success criteria

### Step 2. Design the data model

Goal:

- define all bronze/silver/gold tables before implementation

Deliverable:

- schema document for runs, creatives, personas, context, evaluations, recommendations, and quarantine records

### Step 3. Build the minimal persona library

Goal:

- create 5 strong personas first, expand to 20+ after validation

Recommended starter set (done):

- Researcher ✅
- Price Anchor ✅
- Brand Loyalist ✅
- Skeptic ✅
- Aspirational Buyer ✅

Next priority additions (v2):

- Trend Follower (critical missing archetype for Indian D2C)
- Impulse Buyer
- Pragmatist

Target: 8 archetypes × 3-5 personas each = 20-40 total

Deliverable:

- persona seed JSON or Delta table with rich behavioral fields

### Step 4. Build creative-card extraction + vision-native eval

Goal:

- convert creatives into a normalized structured format
- also pass raw ad image directly to persona evaluation (v2: CreativeCard is supplementary, not sole input)

Fields to extract:

- headline
- body copy
- CTA
- pricing cues (₹-aware for Indian ads)
- urgency cues
- social proof cues
- visual style
- product visibility
- premium/value framing
- Hinglish/regional language detection (v2)

Deliverable:

- creative card schema + extraction notebook/job
- vision-native evaluation path (raw image + CreativeCard to each persona)

### Step 5. Implement bronze ingestion

Goal:

- land all raw assets and metadata into Databricks tables

Deliverable:

- bronze tables and ingestion job

### Step 6. Implement silver transformations and quality controls

Goal:

- standardize and validate all source inputs

Deliverable:

- silver tables
- expectations/assertions
- quarantine workflow

### Step 7. Implement the simulation engine

Goal:

- run each selected persona against a creative card + context payload

Deliverable:

- evaluation outputs table with structured JSON fields

### Step 8. Build gold aggregations

Goal:

- compute segment-level and creative-level metrics

Deliverable:

- action distribution
- sentiment split
- trust / relevance summaries
- overall creative score

### Step 9. Add the agentic decision layer

Goal:

- choose a winning creative and recommend concrete edits

Deliverable:

- recommendation table
- logged agent inputs and outputs

### Step 10. Add dashboard and demo assets

Goal:

- produce a clear stakeholder-facing story

Deliverable:

- dashboard
- demo dataset / demo runs
- screenshots or flow notes for final presentation

### Step 11. Add evaluation and observability

Goal:

- prove the system is inspectable and improving

Deliverable:

- cost log
- run log
- simple evaluation notebook comparing recommendations across runs

## 11. Suggested table inventory

Minimum viable tables:

- `bronze_creative_uploads`
- `bronze_persona_seed`
- `bronze_market_context`
- `silver_creative_cards`
- `silver_personas`
- `silver_market_context`
- `silver_run_cohort`
- `silver_quarantine_records`
- `gold_persona_evaluations`
- `gold_creative_segment_summary`
- `gold_creative_scorecards`
- `gold_agent_recommendations`
- `gold_run_audit_log`

## 12. Success criteria

This project is excellent if the reviewer can immediately see:

1. multiple data inputs are joined meaningfully
2. bronze/silver/gold is visible
3. quality controls are explicit
4. the agent takes a business action
5. the dashboard is clean
6. the business value is obvious

## 13. What not to do

- do not pitch this as a vague AI startup deck only
- do not skip the medallion structure
- do not hide the quality layer
- do not make the agent just summarize
- do not start with 50 personas before the first 5 work well
- do not build a full frontend before the pipeline is stable
- do not let streaming complexity consume the project unless it adds real value

## 14. What Claude Opus should do after this roadmap

Once this roadmap is accepted, the next high-value execution order is:

1. turn this into a detailed technical architecture
2. define the full schema for all bronze/silver/gold tables
3. define the persona JSON schema and starter personas
4. define the creative-card schema
5. define the evaluation output schema
6. design the Databricks jobs / notebooks / DLT flow
7. design the agent input-output contract

## 15. Recommended immediate next step

Next step for us:

Design the exact bronze/silver/gold schema for Synthetic India.

That is the most leverage-heavy next move because it locks the data model, the pipeline boundaries, and the agent interfaces before implementation starts.