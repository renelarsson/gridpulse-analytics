# GridPulse Analytics

This is a streaming-first ISO-NE electricity market analytics project on GCP with Redpanda, PyFlink, BigQuery, dbt, Terraform, and Streamlit.

## Problem Description

The project answers the questions "How do day-ahead wholesale electricity prices vary across ISO-NE locations and across time?" and "Can the same source data be checked in both a streaming path and a warehouse path before it reaches a dashboard?"

That second question matters because the project is not only trying to visualize prices. It is also trying to show that one source file can produce consistent results through two different processing paths:

- a streaming path for event replay and near-real-time style aggregation
- a warehouse path for modeled analytical tables and dashboard queries

If those two paths agree at the same business grain, the dashboard has a stronger validation story than a single-path pipeline.

The first narrow scope uses historical ISO-NE day-ahead hourly LMP data so the full path is reproducible:

- Raw CSV download
- Canonical normalization
- Streaming replay through Redpanda and PyFlink
- Raw warehouse landing with `dlt` into BigQuery
- dbt staging and marts in BigQuery
- Streamlit dashboard backed by the warehouse marts

## Dataset Terms

- ISO-NE: ISO New England, the regional transmission organization that operates the New England bulk electricity market and grid.
- day-ahead: the market in which prices are set before the operating day rather than during live delivery.
- hourly: one value per delivery hour.
- LMP: locational marginal price, the wholesale electricity price at a specific location and hour.
- day-ahead hourly LMP data: a table of hourly wholesale power prices by location for the next operating day.
- mart: a business-facing analytical table built from raw and staging data for a specific reporting use case.

## Scope

This repository is structured for the [Data Engineering Zoomcamp](https://github.com/DataTalksClub/data-engineering-zoomcamp) course capstone:

- Problem description: this README describes the business question, source data, and output contract
- Cloud: BigQuery is the warehouse target on GCP and the repo includes Terraform for the first cloud slice under `infra/terraform/`
- Streaming ingestion: Redpanda plus PyFlink are implemented and validated locally
- Data warehouse: BigQuery raw landing, typed staging, and two marts are implemented; the marts are partitioned and clustered for the main dashboard and slice-and-filter query pattern
- Transformations: dbt models and dbt tests are implemented under `transform/dbt/`
- Dashboard: the Streamlit app in `apps/streamlit/app.py` provides two explicit tiles
- Reproducibility: this README documents commands, reasoning, validation, and expected outcomes in execution order

## Stack

- Cloud: GCP
- Infrastructure as code: Terraform
- Ingestion: `dlt`
- Streaming broker: Redpanda
- Stream processing: PyFlink
- Operational sink: PostgreSQL
- Warehouse: BigQuery
- Transformations: dbt
- Dashboard: Streamlit
- Runtime: Python 3.12 with `uv`

## Architecture

The current reproducible path is:

1. Download one historical ISO-NE day-ahead CSV
2. Normalize the raw vendor format into a stable event schema
3. Replay normalized events into Redpanda
4. Aggregate hourly location metrics in PyFlink and write them to PostgreSQL
5. Load the raw CSV into BigQuery with `dlt`
6. Build dbt staging and marts in BigQuery
7. Serve dashboard tiles from Streamlit

The warehouse and streaming paths meet at the same hourly `location_name` grain in `dbt_iso_ne.mrt_hourly_lmp_by_location` and `stream_hourly_lmp`.

In practice, that means both paths are expected to produce the same kind of row: one hourly aggregate per location for the same market period. That shared output grain makes it possible to compare the streaming result and the warehouse result directly.

## Why Two Paths

Purpose: show that the same source data can be processed consistently in both an event-driven path and an analytical warehouse path before it is presented in the dashboard.

The streaming path is useful for event replay, windowing, and sink validation.

The warehouse path is useful for typed transformations, partitioned analytical tables, and dashboard queries.

Using both paths in the same project makes it possible to compare outputs at a shared hourly location grain instead of trusting only one processing route.

## Repo Areas

- `src/ingestion/`: download, normalization, and `dlt` ingestion
- `src/replay/`: deterministic event replay into Redpanda
- `src/streaming/`: PyFlink hourly aggregation job
- `ops/docker/compose.local.yml`: local Redpanda, PostgreSQL, and Flink stack
- `transform/dbt/`: BigQuery dbt project
- `infra/terraform/`: first GCP Terraform slice
- `apps/streamlit/`: dashboard application
- `markdowns/plan.md`: detailed implementation log and procedure manual

## Prerequisites

### Commands

```bash
python3.12 --version
uv --version
docker --version
docker compose version
git --version
terraform version
```

### Reasoning

These tools cover the current implementation path:

- Python and `uv` run the project code
- Docker Compose runs Redpanda, PostgreSQL, and Flink locally
- Git is needed to clone and review the repo state
- Terraform validates the version-controlled GCP infrastructure slice in `infra/terraform/`

BigQuery access also requires a GCP service-account JSON file.

### Validation

Each command should print a valid version string rather than `command not found`.

### Conclusion

If the prerequisite commands succeed, the local and warehouse reproduction path can run from this repository.

## Clean Start Policy

### Commands

If you are reproducing this repo for the first time on a clean machine, start directly with section 1.

If you are rerunning on a machine that already has prior repo state, use this optional reset first:

```bash
docker compose -f ops/docker/compose.local.yml down
rm -rf .venv .venv-flink
```

### Reasoning

You do not need to delete existing environments or stop Docker containers if the current state is already healthy.

Use the optional reset only when you want a from-scratch reproduction or when an earlier failed run may have left behind conflicting environment or container state.

### Validation

- if `docker compose ... down` completes, the local services are stopped cleanly
- if `.venv` and `.venv-flink` are removed, section 1 will recreate them from scratch

### Conclusion

The default path is to start at section 1 without manual cleanup. The reset is optional, not required.

## 1. Set Up The Python Environments

Purpose: create the two Python runtimes required by the current implementation, one for the main project and one isolated environment for local PyFlink submission.

### Commands

Create and sync the main project environment:

```bash
uv venv --python 3.12 .venv
uv sync
```

Create the dedicated PyFlink environment:

```bash
uv python install 3.11
uv venv --python 3.11 --seed .venv-flink
.venv-flink/bin/python -m pip install 'setuptools<81'
.venv-flink/bin/python -m pip install apache-flink==1.20.1 psycopg[binary]
```

### Reasoning

The main `.venv` is used for ingestion, dbt, BigQuery validation, and Streamlit.

The separate `.venv-flink` keeps PyFlink isolated from the rest of the repo dependencies, which reduces package conflicts during local Flink submission.

The PyFlink package must match the local Docker Flink cluster version. The Compose stack uses Flink `1.20.1`, so the Python environment is pinned to `apache-flink==1.20.1` rather than the latest PyPI release.

The dedicated `.venv-flink` intentionally uses Python `3.11`, even though the rest of the repo uses Python `3.12`. `apache-flink==1.20.1` pulls an `apache-beam` and `numpy` build chain that does not install cleanly on Python `3.12` in this repo's current local flow.

`uv venv` also needs `--seed` here so `pip` is present inside `.venv-flink` before the package install step runs.

The extra `setuptools<81` pin is required because the Beam dependency used by this PyFlink release still imports `pkg_resources`, which is no longer present in newer `setuptools` releases.

### Validation

Check that both interpreters exist:

```bash
test -x .venv/bin/python && echo main-env-ok
test -x .venv-flink/bin/python && echo flink-env-ok
```

### Conclusion

The repo now has the two Python runtimes required by the implemented local stack.

## 2. Prepare The Source Data

Purpose: download the historical source files and normalize them into a stable schema that both the streaming and warehouse paths can use.

### Commands

Download the validated historical raw files:

```bash
uv run python -m src.ingestion.download_day_ahead
uv run python -m src.ingestion.download_day_ahead --report-date 20260318
```

Normalize the first day into canonical event rows:

```bash
uv run python -m src.ingestion.normalize_day_ahead
```

### Reasoning

The project uses historical day-ahead files for the first slice so the end-to-end flow is stable and reviewable.

The normalized file removes report framing and produces a consistent event schema used by the replay path.

### Validation

Check that the expected files exist:

```bash
test -f data/raw/WW_DALMP_ISO_20260317.csv && echo raw-20260317-ok
test -f data/raw/WW_DALMP_ISO_20260318.csv && echo raw-20260318-ok
test -f data/normalized/WW_DALMP_ISO_20260317_normalized.csv && echo normalized-ok
```

### Conclusion

The raw warehouse path and the streaming replay path now share the same validated source family.

## 3. Reproduce The Local Streaming Pipeline

Purpose: prove that the historical source data can be replayed through Redpanda and PyFlink and emitted into a validated PostgreSQL sink.

### Commands

Start the local services:

```bash
docker compose -f ops/docker/compose.local.yml up -d
```

This starts Docker containers, including PostgreSQL on port `5432`. That port is for database clients such as `psql` or Python drivers, not for a web browser. Opening `http://127.0.0.1:5432/` in the browser is therefore expected to show no page or a browser error because PostgreSQL does not speak HTTP.

Fetch the connector JARs required by the PyFlink job:

```bash
bash ops/scripts/fetch_flink_jars.sh
```

Wait for PostgreSQL to accept database connections and for the Flink JobManager REST API to start responding:

```bash
until docker compose -f ops/docker/compose.local.yml exec -T postgres \
pg_isready -U postgres -d market_data >/dev/null 2>&1; do sleep 1; done

until curl -sf http://localhost:8081/jobs/overview >/dev/null; do sleep 2; done
```

Create the Kafka topic and submit the Flink job:

```bash
docker compose -f ops/docker/compose.local.yml exec redpanda rpk topic create day_ahead_events
.venv-flink/bin/python src/streaming/hourly_lmp_job.py --init-postgres-from-host
```

If you are rerunning section 3 after a previous Flink submission, do not submit the job again on top of an already running insert job. Either restart the local stack first with `docker compose -f ops/docker/compose.local.yml down -v` and then bring it back up, or explicitly cancel the earlier Flink job before resubmitting. Otherwise two running jobs will consume the same replay topic and duplicate the sink rows.

Replay the normalized events with the watermark sentinel enabled:

```bash
uv run python -m src.replay.replay_day_ahead \
--input-path data/normalized/WW_DALMP_ISO_20260317_normalized.csv \
--delay-seconds 0 \
--quiet \
--verify-acks \
--acks-timeout-seconds 10 \
--emit-watermark-sentinel
```

### Reasoning

This stage proves the streaming part of the capstone end to end:

- Redpanda receives the historical events
- PyFlink performs hourly tumbling-window aggregation by `location_name`
- PostgreSQL receives the emitted hourly sink rows

The readiness checks matter because `docker compose up -d` only starts the containers. It does not guarantee that PostgreSQL is already accepting connections or that Flink is already ready to accept a submitted job.

The watermark sentinel is a synthetic final replay record emitted after the real input rows. Its job is to push the event-time watermark forward far enough that PyFlink closes and emits the last hourly windows. Without it, a finite replay can end before the final event-time windows are considered complete.

### Validation

Check the sink row count:

```bash
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c "SELECT COUNT(*) AS row_count FROM stream_hourly_lmp;"
```

Check the hourly window profile:

```bash
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c \
"SELECT window_start, COUNT(*) AS row_count FROM stream_hourly_lmp GROUP BY window_start ORDER BY window_start;"
```

The validated result for the current repo state is:

- `29064` sink rows
- `24` hourly windows
- `1211` rows per hourly window

Before moving on to section 4, confirm that the sink row-count query above returns `29064` in the current local run. This verifies that section 3 is fully validated after any rerun or recovery.

### Conclusion

The streaming criterion is satisfied by a real producer, a real stream processor, and a validated streaming sink.

## 4. Reproduce The Raw Warehouse Landings

Purpose: load the same raw source file into a local relational target and the cloud warehouse so the raw contract is validated in both places.

### Commands

Start only the local database service for the local `dlt` raw-landing slice:

```bash
docker compose -f ops/docker/compose.local.yml up -d postgres
until docker compose -f ops/docker/compose.local.yml exec -T postgres \
pg_isready -U postgres -d market_data >/dev/null 2>&1; do sleep 1; done
```

Run the local PostgreSQL raw landing:

```bash
uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw \
--destination postgres \
--destination-dsn postgresql://postgres:postgres@localhost:5432/market_data \
--write-disposition replace
```

Export the GCP service-account path for BigQuery:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/workspaces/de-capstone/my-creds/de-zoomcamp-485107-3cbafa3d7c94.json
```

Run the BigQuery raw landing:

```bash
uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw \
--destination bigquery \
--destination-credentials "$GOOGLE_APPLICATION_CREDENTIALS" \
--write-disposition replace
```

### Reasoning

The local PostgreSQL landing proves the `dlt` source contract in a low-cost and easy-to-inspect way.

Here, `source contract` means the expected raw schema and row shape produced by the ingestion code. `cheaply` means this first validation happens in a local PostgreSQL container instead of immediately using cloud resources. `inspectably` means the loaded rows can be checked directly with simple SQL queries.

The BigQuery landing proves the same raw contract can be moved into the target cloud warehouse without changing the source shape.

### Validation

Check the local PostgreSQL landing:

```bash
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c 'SELECT COUNT(*) AS row_count FROM "iso_ne_raw"."day_ahead_hourly_lmp_raw";'
```

Check the BigQuery landing:

```bash
uv run python - <<'PY'
from google.cloud import bigquery

client = bigquery.Client(project="de-zoomcamp-485107")
query = """
SELECT COUNT(*) AS row_count
FROM `de-zoomcamp-485107.iso_ne_raw.day_ahead_hourly_lmp_raw`
"""
for row in client.query(query).result():
    print(f"row_count={row['row_count']}")
PY
```

The validated result for the current repo state is `29064` rows in both raw landing targets.

### Conclusion

The project now has both a local raw-ingestion proof and a cloud raw-ingestion proof.

## 5. Build The BigQuery dbt Warehouse Layer

Purpose: transform the raw warehouse tables into typed staging and analytics marts that are ready for comparison queries and dashboard use.

### Commands

Point dbt at the repo-local profile:

```bash
export DBT_PROFILES_DIR=/workspaces/de-capstone/transform/dbt/profiles
```

Validate the dbt connection:

```bash
uv run dbt debug --project-dir transform/dbt
```

Build the staging model and marts:

```bash
uv run dbt run --project-dir transform/dbt \
--select stg_iso_ne_day_ahead_hourly_lmp mrt_hourly_lmp_by_location mrt_daily_lmp_summary_by_location
```

Run the dbt tests for the same models:

```bash
uv run dbt test --project-dir transform/dbt \
--select stg_iso_ne_day_ahead_hourly_lmp mrt_hourly_lmp_by_location mrt_daily_lmp_summary_by_location
```

### Reasoning

The warehouse layer has three levels:

- staging: typed source-aligned warehouse fields
- hourly mart: the shared comparison grain between the warehouse and streaming outputs
- daily mart: the first dashboard-facing warehouse model

The marts are configured for the main dashboard query pattern:

- `mrt_hourly_lmp_by_location` is partitioned by `window_start` day and clustered by `location_name`
- `mrt_daily_lmp_summary_by_location` is partitioned by `market_date` and clustered by `location_name`

This means BigQuery stores the tables in a layout that matches the most common filters in this project:

- partitioning keeps rows grouped by day so day-based queries scan less data
- clustering keeps rows with similar `location_name` values physically closer so location filters are more efficient

This matches the expected access pattern of filtering by day and drilling by location.

### Validation

Check row-count parity between raw and staging:

```bash
uv run python - <<'PY'
from google.cloud import bigquery

client = bigquery.Client(project="de-zoomcamp-485107")
query = """
SELECT 'raw' AS layer, COUNT(*) AS row_count
FROM `de-zoomcamp-485107.iso_ne_raw.day_ahead_hourly_lmp_raw`
UNION ALL
SELECT 'staging' AS layer, COUNT(*) AS row_count
FROM `de-zoomcamp-485107.dbt_iso_ne.stg_iso_ne_day_ahead_hourly_lmp`
"""
for row in client.query(query).result():
    print(f"{row['layer']}={row['row_count']}")
PY
```

Check the hourly warehouse mart:

```bash
uv run python - <<'PY'
from google.cloud import bigquery

client = bigquery.Client(project="de-zoomcamp-485107")
query = """
SELECT COUNT(*) AS row_count
FROM `de-zoomcamp-485107.dbt_iso_ne.mrt_hourly_lmp_by_location`
"""
for row in client.query(query).result():
    print(f"hourly_row_count={row['row_count']}")
PY
```

Check the dashboard-facing daily mart:

```bash
uv run python - <<'PY'
from google.cloud import bigquery

client = bigquery.Client(project="de-zoomcamp-485107")
query = """
SELECT COUNT(*) AS row_count
FROM `de-zoomcamp-485107.dbt_iso_ne.mrt_daily_lmp_summary_by_location`
"""
for row in client.query(query).result():
    print(f"daily_row_count={row['row_count']}")
PY
```

Check the warehouse partitioning and clustering metadata:

```bash
uv run python - <<'PY'
from google.cloud import bigquery

client = bigquery.Client(project="de-zoomcamp-485107")
for table_name in [
    "de-zoomcamp-485107.dbt_iso_ne.mrt_hourly_lmp_by_location",
    "de-zoomcamp-485107.dbt_iso_ne.mrt_daily_lmp_summary_by_location",
]:
    table = client.get_table(table_name)
    print(table_name)
    print(f"time_partitioning={table.time_partitioning.field if table.time_partitioning else None}")
    print(f"clustering_fields={table.clustering_fields}")
PY
```

The validated result for the current repo state is:

- raw and staging both contain `29064` rows
- `mrt_hourly_lmp_by_location` contains `29064` rows
- `mrt_daily_lmp_summary_by_location` contains `1211` rows
- the marts are partitioned and clustered for the dashboard's day-and-location query pattern

### Conclusion

The warehouse and transformation criteria are satisfied by real dbt models, real dbt tests, and query-aware BigQuery table design.

## 6. Run The Streamlit Dashboard

Purpose: serve the modeled warehouse outputs through a simple interface with one categorical tile and one temporal tile.

### Commands

Ensure the same GCP credential is exported in the current shell:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/workspaces/de-capstone/my-creds/de-zoomcamp-485107-3cbafa3d7c94.json
```

Start the dashboard:

```bash
uv run streamlit run apps/streamlit/app.py \
--server.address 0.0.0.0 \
--server.port 8501
```

### Reasoning

The dashboard reads directly from the validated dbt marts in BigQuery, so it shows the same modeled warehouse outputs that were already tested.

The app exposes two explicit tiles required by the rubric guidance:

- Tile 1: a categorical distribution chart showing top locations by average daily LMP
- Tile 2: a temporal line chart showing hourly average LMP across the selected market day for one location

### Validation

Check syntax before launch:

```bash
/workspaces/de-capstone/.venv/bin/python -m py_compile apps/streamlit/app.py
```

Check that the Streamlit server starts:

```bash
curl -I http://localhost:8501
```

Expected success signal:

- `HTTP/1.1 200 OK`

In the UI, confirm all of the following:

- the app loads without a BigQuery auth error
- the sidebar shows configurable BigQuery project and table inputs
- the categorical tile renders a bar chart
- the temporal tile renders a line chart
- the detailed tables show the underlying daily and hourly rows used by the charts

### Conclusion

The dashboard criterion is satisfied by a real Streamlit app with two dashboard tiles backed by warehouse models rather than ad hoc SQL inside the UI.

## 7. Inspect The Terraform Slice

Purpose: show that the current cloud warehouse slice is also represented as version-controlled infrastructure, not only as manual setup steps.

### Commands

Read the Terraform slice:

```bash
sed -n '1,220p' infra/terraform/README.md
sed -n '1,220p' infra/terraform/main.tf
sed -n '1,220p' infra/terraform/variables.tf
```

If Terraform is installed on your machine, validate it:

```bash
cd infra/terraform
terraform init -backend=false
terraform validate
```

### Reasoning

The Terraform scope is intentionally narrow but real. It codifies the BigQuery raw dataset, the raw-loader service account, and the minimum IAM needed for the warehouse cloud path.

### Validation

The repo should show Terraform resources for:

- `google_bigquery_dataset`
- `google_service_account`
- `google_project_iam_member`
- `google_bigquery_dataset_iam_member`

### Conclusion

The cloud and IaC criteria are covered by the implemented GCP warehouse path plus the version-controlled Terraform slice.

The current validated result for this repo state is:

- Terraform CLI installed successfully
- `terraform init -backend=false` succeeded in `infra/terraform`
- `terraform validate` returned `Success! The configuration is valid.`

## Current Verified Outputs

- Local streaming sink `stream_hourly_lmp`: `29064` rows, `24` hourly windows, `1211` rows per window
- BigQuery raw landing `iso_ne_raw.day_ahead_hourly_lmp_raw`: `29064` rows
- BigQuery staging model `dbt_iso_ne.stg_iso_ne_day_ahead_hourly_lmp`: `29064` rows
- BigQuery hourly mart `dbt_iso_ne.mrt_hourly_lmp_by_location`: `29064` rows
- BigQuery daily mart `dbt_iso_ne.mrt_daily_lmp_summary_by_location`: `1211` rows

## Final Reproduction Order

If you want the shortest reproducible path through the repo, follow the stages in this exact order:

1. set up the Python environments
2. download and normalize the source files
3. run the local streaming pipeline
4. run the local and cloud raw landings
5. build and test the dbt warehouse layer
6. run the Streamlit dashboard
7. inspect or validate the Terraform slice

## Conclusion

This repository now demonstrates an end-to-end capstone with all rubric categories represented in code and in documentation: a clearly stated problem, GCP usage with Terraform, streaming ingestion, a modeled BigQuery warehouse, dbt transformations, a two-tile Streamlit dashboard, and a reproducible README that records the commands and validations needed for a reviewer to rerun the project.

## Images

### Screenshots

![Screenshot 2026-03-30 191258](images/Screenshot%202026-03-30%20191258.png)

![Screenshot 2026-03-30 191429](images/Screenshot%202026-03-30%20191429.png)

![Screenshot 2026-03-30 191501](images/Screenshot%202026-03-30%20191501.png)

![Screenshot 2026-03-30 191538](images/Screenshot%202026-03-30%20191538.png)

![Screenshot 2026-03-30 193445](images/Screenshot%202026-03-30%20193445.png)

### Diagrams

**Architecture Evolution:**

![Step 1 to 7 architecture evolution](images/step-1-to-7-architecture-evolution.png)

**Service Flow:**

![Step 1 to 7 service flow](images/step-1-to-7-service-flow.png)

