# de-capstone Logs

## Purpose

This file consolidates the supporting planning notes into one working log so the repo can be managed through four primary markdown documents:

1. `README.md`
2. `plan.md`
3. `TODOS.md`
4. `logs.md`

The original supporting markdown files are retained for traceability, but this document is now the main consolidated reference for the material that had been split across multiple planning notes.

## Current Documentation Decision

- the first implementation pass is now narrowed to historical ISO-NE day-ahead hourly data only
- real-time hourly data remains a later extension after the base local path is stable

## Current Runtime Status

- the first local replay-to-Flink-to-PostgreSQL slice is now validated
- replay validation completed with `input_rows=29064 sent=29064 acked=29064`
- PostgreSQL validation completed with `26642` rows in `stream_hourly_lmp`
- the first local `dlt` raw-ingestion slice is now validated in PostgreSQL
- append-mode backfill was validated with two raw files and `58128` total rows in the append test table
- the first BigQuery raw landing is now validated with `29064` rows in `de-zoomcamp-485107.iso_ne_raw.day_ahead_hourly_lmp_raw`

## Chapter 1: Dataset Validation

### Purpose

Validate ISO New England as the primary capstone dataset and decide whether the first implementation slice should rely on public report downloads, authenticated web services, or a hybrid of both.

### Validation Outcome

ISO-NE is usable for this capstone from Denmark, but with an important caveat:

- the public pricing page is reachable without login
- at least one public historical CSV path is reachable without login
- at least one current CSV transform endpoint returned `403 Forbidden` from this environment
- the authenticated ISO-NE Web Services API exists and exposes the right LMP resources, but it requires signup and HTTP Basic Authentication

That means the dataset is still viable, but the safest first implementation path is:

1. start with reachable historical CSV reports for validation and replay
2. treat authenticated web services as the upgrade path for cleaner incremental ingestion
3. do not assume every `transform/csv/...` endpoint is publicly automatable from every location or runtime

### Denmark-Specific Assessment

Being seated in Denmark is not, by itself, a blocker.

What was validated from this environment:

- `https://www.iso-ne.com/isoexpress/web/reports/pricing` returned `200 OK`
- `https://www.iso-ne.com/histRpts/da-lmp/WW_DALMP_ISO_20260317.csv` returned `200 OK`
- `https://www.iso-ne.com/transform/csv/fiveminlmp/current?type=prelim` returned `403 Forbidden`

Interpretation:

- ISO-NE public web content is reachable internationally
- historical report downloads can be reachable without credentials
- some live or transformed endpoints may be protected, rate-limited, or otherwise not suitable as anonymous public ingestion sources

### Recommended First-Slice Dataset Strategy

#### Primary first slice

Use public historical LMP reports to prove:

- source accessibility
- schema extraction
- replay-based streaming feasibility
- warehouse and analytics model design

#### Upgrade path

If you want true incremental ingestion rather than replay-first simulation, apply for ISO-NE Web Services access and use the authenticated REST API for LMP endpoints.

#### Fallback posture

If authenticated ISO-NE access becomes too slow or brittle, keep ISO-NE as the analytical domain but use reachable historical reports for replay and add EIA as context enrichment rather than switching domains.

### Candidate Sources For The First Implementation Slice

#### Publicly reachable in this validation pass

1. Pricing reports landing page:
   `https://www.iso-ne.com/isoexpress/web/reports/pricing`
2. Historical day-ahead hourly LMP CSV example:
   `https://www.iso-ne.com/histRpts/da-lmp/WW_DALMP_ISO_20260317.csv`
3. Historical real-time hourly final LMP CSV example:
   `https://www.iso-ne.com/histRpts/rt-lmp/lmp_rt_final_20260315.csv`
4. Public pricing page path patterns discovered:
   - `/static-transform/csv/histRpts/da-lmp/WW_DALMP_ISO_20260317.csv`
   - `/static-transform/csv/histRpts/rt-lmp/lmp_rt_final_20260315.csv`

#### Exposed by authenticated web services documentation

1. Five-minute LMP: `/fiveminutelmp`
2. Five-minute preliminary or final variants: `/fiveminutelmp/{Type}/...`
3. Hourly day-ahead LMP final: `/hourlylmp/da/final/...`
4. Hourly real-time LMP prelim: `/hourlylmp/rt/prelim/...`
5. Locations reference: `/locations` and `/locations/all`

Base path for authenticated web services:

- `https://webservices.iso-ne.com/api/v1.1`

### Sample Schema Confirmed

The reachable historical day-ahead hourly CSV included this header structure:

- `Date`
- `Hour Ending`
- `Location ID`
- `Location Name`
- `Location Type`
- `Locational Marginal Price`
- `Energy Component`
- `Congestion Component`
- `Marginal Loss Component`

### Event Grain

Confirmed immediately:

- day-ahead hourly LMP reports support an hourly grain immediately
- historical real-time hourly LMP reports also support an hourly grain immediately

Working first-pass decision:

- implement with day-ahead hourly only
- keep five-minute real-time LMP as the long-term target event stream
- add real-time hourly only after the day-ahead path is stable

### Metric And Dimension Fit

The dataset clearly supports categorical analysis through:

- `Location ID`
- `Location Name`
- `Location Type`

Confirmed or documented measure fields relevant to the capstone:

- total locational marginal price
- energy component
- congestion component
- marginal loss component

### Replay Feasibility

Replay is a practical and defensible first implementation pattern because reachable historical CSVs can seed the stream, replay gives deterministic demos, and replay still supports a streaming-first architecture when Redpanda and PyFlink process interval events in event time.

### Risks And Mitigations

#### Risk: live endpoint restrictions

- evidence: current five-minute transform CSV returned `403 Forbidden`
- mitigation: start with reachable historical CSVs and treat web services as a later authenticated enhancement

#### Risk: schema differences between report families

- evidence: public reports and web services are delivered through different surfaces
- mitigation: lock the first slice to one report family before broadening coverage

#### Risk: overcommitting to live ingestion too early

- mitigation: build the first streaming demo as replay-first, then add authenticated incrementals if needed

### Recommended Decision

Proceed with ISO-NE as the primary dataset.

For the first implementation slice:

1. use historical day-ahead hourly LMP CSVs only
2. design the schema around `Date`, `Hour Ending`, location fields, and LMP component fields
3. keep five-minute real-time LMP as the target future stream, but do not block progress on anonymous access to current transform endpoints

## Chapter 2: Architecture Note

### Purpose

Define the architecture for the capstone project, aligning with the streaming-first approach and the approved stack, while keeping the first implementation slice narrow.

### High-Level Architecture

This project has two architectural tracks that work together:

1. the runtime data path for ingestion, streaming, storage, transformation, and presentation
2. the control path for provisioning and scheduled orchestration

### Data Flow

1. source: ISO-NE day-ahead market reports first, then later broader ISO-NE feeds
2. ingestion: dlt pipelines load historical and incremental data into GCS and BigQuery
3. streaming: Redpanda publishes interval market events
4. stream processing: PyFlink computes windowed metrics and anomaly logic
5. operational sink: PostgreSQL stores near-real-time outputs
6. warehouse: BigQuery integrates raw, stream, and transformed data
7. dashboard: Streamlit visualizes analytics-ready data

### Control Flow

1. provisioning: Terraform defines and manages GCP resources
2. scheduled orchestration: Kestra triggers non-streaming jobs such as dlt runs, warehouse syncs, and dbt runs
3. always-on streaming: Redpanda and PyFlink remain logically separate from Kestra-triggered schedules

### Component Boundaries

#### Ingestion Layer

- tool: dlt
- purpose: load historical and incremental data into raw storage
- output: GCS and BigQuery raw tables

#### Infrastructure Layer

- tool: Terraform
- purpose: provision and version control the GCP project resources needed by the capstone
- planned scope: GCS buckets, BigQuery datasets, service accounts, IAM bindings, and later deployment resources if the dashboard is hosted on GCP

#### Streaming Layer

- tool: Redpanda
- purpose: publish interval market events for real-time processing
- output: streamed events consumed by PyFlink

#### Stream Processing Layer

- tool: PyFlink
- purpose: compute windowed aggregates, anomalies, and spreads
- output: PostgreSQL tables for near-real-time results

#### Warehouse Layer

- tool: BigQuery
- purpose: integrate raw, stream, and transformed data
- output: analytics-ready marts for dashboard consumption

#### Transformation Layer

- tool: dbt
- purpose: build staging, intermediate, and mart models
- output: BigQuery tables optimized for analytics

## Session Update: 2026-03-18 Local Ingestion Slice

- Step 4 and Step 5 were implemented for the first local pass.
- Added [src/schema/iso_ne_day_ahead_schema.py](../src/schema/iso_ne_day_ahead_schema.py) with the first canonical field list and `construct_market_timestamp_utc` helper.
- Added [src/ingestion/download_day_ahead.py](../src/ingestion/download_day_ahead.py) for quick local download testing with the chosen ISO-NE day-ahead sample.
- Added [src/ingestion/normalize_day_ahead.py](../src/ingestion/normalize_day_ahead.py) to convert the raw CSV into canonical output under `data/normalized/`.
- Confirmed the ISO-NE report structure for this file family: metadata rows, field-name row, field-type row, then `D` data rows.
- Confirmed the source date format for this report family is `MM/DD/YYYY`.
- Confirmed the source timezone assumption for market timestamps is New England local market time, implemented as `America/New_York`, then converted to UTC.
- `market_type` is currently populated during normalization as a static `day-ahead` value.
- `source_file` is currently populated during normalization from the input file path.
- `ingest_run_id` is currently generated once per normalization run as a UUID and applied to all rows in that run.
- Validated local commands:
  - `uv run python -m src.ingestion.download_day_ahead`
  - `uv run python -m src.ingestion.normalize_day_ahead`
- Validated output file: `data/normalized/WW_DALMP_ISO_20260317_normalized.csv`
- Next required milestone remains Step 6: stand up the local Redpanda, PostgreSQL, and Flink container stack.

## Session Update: 2026-03-24 Step 8 Runtime Validation

- Step 8 was executed with the existing local Docker Compose stack plus the dedicated `.venv-flink` environment.
- The working Step 8 submission command was:
  - `source .venv-flink/bin/activate && python src/streaming/hourly_lmp_job.py --init-postgres-from-host`
- The connector JARs required by the PyFlink job were downloaded into `ops/flink/jars/` with `bash ops/scripts/fetch_flink_jars.sh`.
- The job was confirmed in the Flink UI and through the REST endpoint at `http://localhost:8081/jobs/overview` with state `RUNNING`.
- The Step 8 source topic `day_ahead_events` was verified through the Redpanda container rather than through a host-installed `rpk` binary.
- Replay validation with `uv run python -m src.replay.replay_day_ahead --input-path data/normalized/WW_DALMP_ISO_20260317_normalized.csv --delay-seconds 0 --quiet --verify-acks --acks-timeout-seconds 10` produced `input_rows=29064 sent=29064 acked=29064`.
- PostgreSQL sink validation through the PostgreSQL container returned `26642` rows in `stream_hourly_lmp` after the replay completed.
- The Flink UI showed non-zero `Records Sent` and `Records Received` values during replay, confirming that records moved through both the source and sink operators.
- Sample sink output confirmed one emitted row per location per hour, for example rows in the `2026-03-17 11:00:00` to `2026-03-17 12:00:00` window with populated `avg_lmp_total`, `max_lmp_total`, and `row_count` values.
- Operational note: host package installation attempts can surface `dpkg` lock, `debconf` lock, or `invoke-rc.d` warnings. Those are package-management issues and are not evidence that the Step 8 PyFlink path is broken.
- Operational note: the observed Redpanda DNS-resolution issue was a broker address or advertised-host mismatch between client context and Docker networking, not a failure caused by the final `hourly_lmp_job.py` submission command.

## Session Update: 2026-03-25 Step 10 and Step 11A Validation

- Step 10 append-mode follow-up was validated with a safe two-step self-test rather than a dropped-table append-only rerun.
- The working pattern was:
  - load `data/raw/WW_DALMP_ISO_20260317.csv` into `iso_ne_raw.day_ahead_hourly_lmp_raw_append_test` with `--write-disposition replace`
  - append `data/raw/WW_DALMP_ISO_20260318.csv` into the same table with `--write-disposition append`
- PostgreSQL validation confirmed `29064` rows from each source file and `58128` total rows in the append test table.
- Runtime lesson: if PostgreSQL is started immediately before a `dlt` run, wait for `pg_isready` before rerunning after any `connection refused` or `server closed the connection unexpectedly` failure.
- Runtime lesson: if Docker reports an OCI runtime error with `container with given ID already exists`, remove the stale PostgreSQL container with `docker rm -f docker-postgres-1` and start the service again.
- Step 11A BigQuery raw landing was rerun successfully with:
  - destination `bigquery`
  - dataset `iso_ne_raw`
  - table `day_ahead_hourly_lmp_raw`
  - credential file `my-creds/de-zoomcamp-485107-3cbafa3d7c94.json`
- `src.ingestion.dlt_raw_ingestion.py` was updated so a BigQuery service-account file path is read as JSON before being passed into `dlt`.
- BigQuery validation succeeded with the shell-based Python client query and returned `row_count=29064` for `de-zoomcamp-485107.iso_ne_raw.day_ahead_hourly_lmp_raw`.
- Operational note: the `google-cloud-bigquery-storage is not installed` message was non-blocking for the successful Step 11A load.

#### Orchestration Layer

- tool: Kestra
- purpose: schedule and coordinate non-streaming jobs
- planned scope: dlt backfills, warehouse syncs, dbt runs, and optional demo lifecycle workflows
- boundary: Kestra is not the stream processor

#### Presentation Layer

- tool: Streamlit
- purpose: visualize data with categorical and temporal views
- output: user-facing dashboard

### Key Decisions

#### Streaming-First Posture

- why: five-minute granularity remains the best final use case even though the first slice is hourly replay
- impact: prioritizes Redpanda and PyFlink over batch pipelines

#### Operational Sink

- choice: PostgreSQL for near-real-time outputs
- alternative: direct BigQuery ingestion deferred until later

#### Warehouse Optimization

- partitioning: event date
- clustering: market type and location

#### Provisioning And Orchestration

- Terraform is included because the approved capstone direction is GCP-based and should be reproducible
- Kestra is included because non-streaming runs still need a clear orchestration story even in a streaming-first project

### Risks And Mitigations

- dataset instability: validate ISO-NE endpoints and schema early
- high latency: optimize Redpanda and PyFlink only after the local path works
- schema evolution: use dlt and dbt to manage schema drift


## Chapter 3: Local Workflow And Repo Structure

### Purpose

Define the local-first working model for the capstone before implementation starts.

This section gives `uv`, Docker Compose, future Make targets, and future CI/CD a clear place in the planning set so the implementation milestone does not begin with toolchain ambiguity.

### Local-First Decision

The first implementation milestone should be local-first because the dataset access path is already validated locally through reachable historical files, replay-based streaming can be proven without early cloud complexity, and toolchain issues should be isolated before Terraform and GCP become part of the debugging surface.

### Baseline Local Tooling

#### Python

- baseline runtime: Python 3.12
- package and environment tool: `uv`

Planned use of `uv`:

- create and manage the project environment
- install runtime and development dependencies
- run Python entry points consistently

#### Containers

- orchestrate local services with Docker Compose

Planned services for milestone one:

- Redpanda
- PostgreSQL
- Flink components needed for PyFlink execution

#### Task runner

- add a `Makefile` later, after the first commands are stable

#### CI/CD

- add GitHub Actions after the local workflow is repeatable

Planned CI/CD scope later:

- linting
- tests
- Terraform formatting and validation
- optional dbt validation when the dbt layer exists

### Proposed Repo Structure

```text
markdowns/
  README.md
  plan.md
  TODOS.md
  logs.md

src/
  ingestion/
  replay/
  streaming/
  schema/

infra/
  terraform/

orchestration/
  kestra/

transform/
  dbt/

apps/
  streamlit/

ops/
  docker/
  scripts/

tests/
  unit/
  integration/

.github/
  workflows/

Makefile
```

### Local Workflow For Milestone One

1. initialize the project with Python 3.12 under `uv`
2. use Docker Compose to start Redpanda, PostgreSQL, and Flink services
3. download a reachable ISO-NE day-ahead sample
4. normalize it into the milestone event schema
5. publish the normalized sample into Redpanda
6. run one PyFlink aggregation job
7. verify sink output in PostgreSQL
8. wrap stable commands in Make only after they are proven

## Chapter 4: Analytics Framing

### Purpose

Lock the business grain and first analytical questions for the first capstone milestone.

### Business Grain

The business grain for the first milestone is one market interval per location per market type.

For the first demo slice, that interval will be hourly because the currently validated reachable files are hourly historical reports.

### Core Questions For Milestone One

The first demo slice should answer these three questions:

1. which ISO-NE locations have the highest hourly LMP values over the selected sample window
2. how does hourly LMP change over time for a selected location or small group of locations
3. where do unusually high hourly prices appear in the sample window

The earlier day-ahead versus real-time comparison question is now deferred until after the day-ahead-only path is stable.

### First Dashboard Views

#### First categorical view

Top locations by hourly LMP over the selected period.

Recommended dimensions and metrics:

- dimension: `location_name`
- optional filter: `market_type`
- metric: max or average `lmp_total`

#### First temporal view

Hourly LMP trend for one selected location over time.

Recommended dimensions and metrics:

- x-axis: `market_timestamp_utc`
- metric: `lmp_total`
- filters: `location_name`, `market_type`

### Milestone-One Spike Definition

A spike is an hourly `lmp_total` above the 95th percentile within the selected sample window.

### Success Interpretation

The milestone is analytically successful if it can:

1. rank locations by price
2. show hourly price movement over time
3. identify a small number of unusually high-price intervals

## Chapter 5: Validation Checklist

### Purpose

Provide a concrete checklist for validating the first local implementation pass.

### Stage 1: Source Validation

- [ ] the chosen historical ISO-NE file URLs are reachable from the working environment
- [ ] the files download twice in a row without manual intervention
- [ ] the report family and market type are documented
- [ ] the source file names are recorded for reproducibility

### Stage 2: Schema Validation

- [ ] raw headers are captured in repo docs
- [ ] `Date` and `Hour Ending` mapping to one event timestamp is documented
- [ ] field names for location and LMP components are normalized
- [ ] the normalized event schema is stable for the chosen sample files
- [ ] timezone handling is explicit

### Stage 3: Local Runtime Validation

- [ ] Python 3.12 environment starts successfully under `uv`
- [ ] Docker Compose starts the required local services
- [ ] Redpanda is reachable locally
- [ ] PostgreSQL is reachable locally
- [ ] Flink components required for the first job are reachable locally

### Stage 4: Replay Validation

- [ ] normalized events can be produced in deterministic order
- [ ] the replay topic name is documented
- [ ] produced event count equals parsed input row count
- [ ] replay can be repeated without silent duplication assumptions

### Stage 5: Stream Processing Validation

- [ ] one PyFlink job starts successfully
- [ ] the job uses the documented event-time field
- [ ] the selected windowing logic is documented
- [ ] the output row count is plausible for the sample size and window definition

### Stage 6: Sink Validation

- [ ] PostgreSQL sink table exists with documented columns
- [ ] stream output rows land in PostgreSQL
- [ ] one verification query is documented and repeatable
- [ ] sink results reflect the chosen aggregation logic

### Stage 7: Analytics Validation

- [ ] the first categorical analytical question can be answered from the validated output
- [ ] the first temporal analytical question can be answered from the validated output or a documented next-step query path
- [ ] the milestone spike definition can be computed or clearly staged for the next increment

### Stage 8: Reproducibility Validation

- [ ] the exact files used are documented
- [ ] the exact commands used are documented
- [ ] open issues and unresolved decisions are documented
- [ ] the next expansion step is explicit

### Definition Of Done For The First Local Pass

The first local implementation pass is done when:

1. historical ISO-NE day-ahead sample files are reproducibly downloadable
2. the sample is normalized into a stable event schema
3. replay into Redpanda is deterministic
4. one PyFlink aggregation runs successfully
5. results land in PostgreSQL and can be queried
6. the milestone’s first business questions can be answered from the output
7. the process is documented clearly enough to repeat


## Chapter 6: Milestone 01 Smallest Demo Slice

### Purpose

Define the smallest implementation slice that proves the capstone direction without depending on live anonymous ISO-NE endpoints.

### Milestone Decision

The first demo slice will use reachable historical ISO-NE day-ahead hourly LMP reports and replay those records through the streaming stack.

Why this is the right first slice:

1. the dataset is already validated as reachable in historical report form
2. replay-based streaming avoids blocking on live endpoint restrictions
3. hourly reports are sufficient to prove ingestion, schema design, replay, transformation, and visualization flow
4. the architecture remains streaming-first because events still move through Redpanda and PyFlink in event time

### Included Scope

#### Source data

- historical day-ahead hourly LMP CSVs from ISO-NE

#### Core flow to prove

1. download a small historical ISO-NE report sample
2. normalize rows into a stable event schema
3. land raw data in a local-first pipeline path
4. replay the normalized records into Redpanda
5. run one PyFlink aggregation over the replayed stream
6. persist stream output to PostgreSQL
7. document the first analytical output and validation results

### Excluded Scope

- live anonymous five-minute endpoint ingestion
- real-time hourly comparison in the first pass
- full Terraform rollout
- full Kestra orchestration
- full dbt project build-out
- full Streamlit dashboard build-out
- advanced anomaly detection logic

### Recommended Dataset Slice

- primary file family: day-ahead hourly LMP historical CSVs
- initial sample size: start with 1 to 3 days of data, not a full month

### Proposed Event Schema

The first normalized event should include:

- `market_date`
- `hour_ending`
- `market_timestamp_utc`
- `market_type`
- `location_id`
- `location_name`
- `location_type`
- `lmp_total`
- `energy_component`
- `congestion_component`
- `marginal_loss_component`
- `source_file`
- `ingest_run_id`

### Minimal Success Criteria

This milestone is complete when all of the following are true:

1. a small ISO-NE historical sample can be downloaded repeatedly
2. the sample can be parsed into a documented normalized schema
3. a deterministic replay can publish the sample into Redpanda
4. one PyFlink job can aggregate the replayed events
5. the aggregation result can be inspected in PostgreSQL
6. the repo documents the exact commands, files, and validation checks used

### Recommended First Aggregation

Use one simple, defensible aggregation for milestone one:

- average or max LMP by location over a tumbling window during replay

### Step-By-Step Procedure

1. lock the sample files
2. define the normalized schema
3. stand up the local runtime
4. prove deterministic replay
5. run one stream aggregation
6. capture milestone evidence

### Risks

- timestamp ambiguity between `Date` and `Hour Ending`
- overbuilding too soon
- local tooling drift
