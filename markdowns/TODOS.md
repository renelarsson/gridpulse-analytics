# de-capstone TODOs

## Status Key

- `[ ]` not started
- `[-]` in progress
- `[x]` done

## Current Focus

This file tracks planning and implementation-readiness tasks only. It should stay ahead of the codebase and make the next decision obvious.

## Phase 1: Repo Planning Baseline

- [x] Confirm that `/workspaces/de-capstone` is the capstone repo root.
- [x] Record the approved stack: GCP, Streamlit, dlt, streaming-first, Python 3.12.
- [x] Mark `data-engineering-zoomcamp/` and `homework/` as reference-only folders.
- [x] Populate `plan.md` with repo-specific project direction.
- [x] Add `.github/copilot-instructions.md` for future agent alignment.
- [x] Create a root task tracker for planning-first execution.

## Phase 2: Dataset Framing

- [x] Write a one-page dataset-validation brief for the primary ISO-NE source.
- [x] List the exact source endpoints or reports that are candidates for ingestion.
- [x] Identify the event timestamp field and expected event grain.
- [x] Confirm which location fields can support categorical dashboard views.
- [x] Record optional enrichment sources, with EIA first if needed.
- [x] Define the fallback plan if the preferred ISO-NE automation path is unstable.

## Phase 3: Analytics Framing

- [x] Lock the business grain for the project.
- [x] Define 2 to 3 core analytical questions the capstone must answer.
- [x] Define the first dashboard categorical view.
- [x] Define the first dashboard temporal view.
- [x] Describe what counts as a spike, spread, or anomaly in project terms.

## Phase 4: Architecture Planning

- [x] Write an architecture note at the repo root.
- [x] Confirm the raw layer flow: source to dlt to GCS and BigQuery.
- [x] Confirm the streaming flow: replay or producer to Redpanda to PyFlink.
- [x] Confirm the stream sink path before BigQuery sync.
- [x] Confirm the analytics flow: BigQuery to dbt to Streamlit.
- [x] Document why the architecture is streaming-first instead of batch-first.

## Phase 5: Implementation Readiness

- [x] Propose a capstone folder structure under the repo root.
- [x] Define local environment assumptions for Python 3.12, Docker, and `uv`.
- [x] Write a milestone-by-milestone validation checklist.
- [x] Define the smallest end-to-end demo slice.
- [x] Decide which parts will be local-only first and which target GCP immediately.

## Deferred Until Explicit Implementation Start

- [x] Create ingestion code with dlt.
- [ ] Create Terraform for GCP resources.
- [x] Create Redpanda producer or replay tooling.
- [x] Create PyFlink jobs.
- [ ] Create dbt project assets.
- [ ] Create Streamlit application code.

## Decision Reminders

- Use dlt, not Bruin, unless the user changes direction.
- Keep the project streaming-first.
- Keep Python 3.12 as the baseline.
- Keep GCP as the default target.
- Keep course and homework material as references, not deliverables.

## Next Best Step

- [x] Decide whether the first implementation pass should include both day-ahead and real-time hourly files or start with day-ahead only.
- [x] Create and validate a local day-ahead sample download script.
- [x] Create and validate a local day-ahead normalization script.
- [x] Stand up the local container stack for Redpanda, PostgreSQL, and Flink.
- [x] Record the Step 9 PostgreSQL validation queries and their expected result shape.
- [x] Introduce the first `dlt` raw-ingestion slice on top of the already validated local source contract.
- [x] Validate append-mode backfill for multiple raw files in the local `dlt` path.
- [x] Validate the first BigQuery raw landing for the Step 11A warehouse path.
- [ ] Codify the validated BigQuery dataset and service-account setup in Terraform.
- [ ] Add the first dbt staging model on top of `iso_ne_raw.day_ahead_hourly_lmp_raw`.
- [ ] Define the first explicit convergence point between the streaming output and the warehouse output.