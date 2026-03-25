# de-capstone

Data Engineering Zoomcamp capstone focused on wholesale electricity market analytics with a streaming-first architecture.

## What A Reviewer Should Know First

This repository has moved from documentation-only planning into the first narrow local implementation slice. The project direction is locked, the first dataset slice is chosen, and the first local download-and-normalize path is now working.

Step 8 is now complete for the first local streaming slice:

- normalized ISO-NE day-ahead events were replayed into Redpanda
- the PyFlink job consumed those events and emitted hourly aggregates
- PostgreSQL validation confirmed `26642` rows in `stream_hourly_lmp`
- the Flink UI showed non-zero `Records Sent` and `Records Received` during replay

The first implementation pass will use historical ISO-NE day-ahead hourly LMP data only. That is a deliberate scope cut so the project can move from planning into development without blocking on unstable anonymous live endpoints.

## Capstone Goal

Build a reproducible pipeline that can:

1. ingest ISO-NE market data
2. replay it through a streaming stack
3. compute windowed price metrics
4. land analytical results in the warehouse path
5. expose those results in a reviewer-friendly dashboard

## Approved Stack

- cloud target: GCP
- ingestion: dlt
- stream broker: Redpanda
- stream processing: PyFlink
- operational sink: PostgreSQL
- warehouse: BigQuery
- transformation: dbt
- dashboard: Streamlit
- infrastructure: Terraform
- orchestration for non-streaming work: Kestra
- baseline Python version: 3.12
- local environment tool: `uv`
- local service runner: Docker Compose

## Current Scope And Status

### What is already decided

- the capstone lives at the repository root
- `data-engineering-zoomcamp/` and `homework/` are reference-only for this capstone
- the project stays streaming-first
- the first runnable slice is local-first
- the first source family is historical ISO-NE day-ahead hourly CSV files

### What is implemented now

- a schema module for the first canonical day-ahead event shape
- a local download script for one historical ISO-NE day-ahead CSV sample
- a local normalization script that converts the raw sample into canonical output
- replay tooling for loading normalized events into Redpanda
- a first PyFlink job that computes hourly aggregates into PostgreSQL
- validated local commands for the first raw-to-normalized and first stream-processing workflows
- validated end-to-end local output in PostgreSQL from the replayed Redpanda topic through the running Flink job
- a `dlt` raw-ingestion entry point for PostgreSQL and BigQuery
- validated local append-mode backfill for the raw `dlt` path
- a validated first BigQuery raw landing for the warehouse path

### What is not implemented yet

- Terraform
- dbt models
- Streamlit app

That is expected. The current documentation set now supports both planning and the first verified local implementation slice.

## How To Use This Documentation Set

Use the markdown files in this order:

1. `README.md` for the project summary and reviewer recipe
2. `plan.md` for the full sequential implementation manual
3. `logs.md` for the consolidated supporting notes and rationale
4. `TODOS.md` for task tracking only

## Reproducibility Recipe

### Stage 1: Verify the host toolchain

Before creating project code, verify that the machine has the expected baseline:

- Python 3.12
- `uv`
- Docker and Docker Compose
- Git
- later, when cloud work starts: GCP CLI and Terraform

The exact command flow is recorded in `plan.md`.

### Stage 2: Follow the implementation manual

`plan.md` is the procedural source of truth. It records, in order:

1. how to prepare the local environment
2. how to create the repo structure
3. how to define the day-ahead sample path
4. how to create the first scripts
5. how to start the local containers
6. how to validate replay and streaming behavior
7. how to expand to cloud components later

### Stage 3: Use the logs as the rationale layer

`logs.md` consolidates the supporting material that explains why the first slice is day-ahead hourly only, why the architecture is streaming-first, and what counts as a successful first pass.

### Stage 4: Validate against the checklist

After implementation starts, the validation points in `logs.md` and the task tracking in `TODOS.md` should be used to confirm that the repo is reproducible rather than merely executable on one machine.

## Repo Working Model

The practical working model for the next phase is:

1. implement locally first
2. prove the path with one small historical day-ahead sample
3. document exact commands and outputs
4. only then widen scope to real-time data, dbt, Terraform, Kestra, and Streamlit

## Expected Near-Term Deliverable

The first narrow end-to-end local demo now proves this path:

1. downloads a day-ahead hourly ISO-NE sample
2. normalizes it into a canonical event schema
3. replays those events into Redpanda
4. runs one PyFlink aggregation
5. writes results to PostgreSQL
6. records all commands and validation steps in the repo

This end-to-end slice is now validated, with Step 8 and Step 9 runtime checks recorded in `plan.md` and `logs.md`.

## Expected Next Deliverable

The next real deliverable is to extend the now-validated local and first-cloud warehouse path without widening scope into dashboards or full infrastructure.

The most relevant next project steps from the current state are:

1. codify the validated BigQuery dataset and service-account setup in Terraform
2. add the first dbt staging model on top of `iso_ne_raw.day_ahead_hourly_lmp_raw`
3. define the first explicit convergence point between the warehouse track and the streaming track

## End-to-End Workflow

The smallest repeatable workflow across the current implemented steps is:

1. Step 5 normalizes the raw ISO-NE CSV into `data/normalized/WW_DALMP_ISO_20260317_normalized.csv`.
2. Step 8 replays that normalized file into Redpanda and runs the PyFlink hourly aggregation into PostgreSQL.
3. Step 9 validates the streaming sink table in PostgreSQL.
4. Step 10 loads the raw CSV itself through `dlt` into the warehouse-style raw table.
5. Step 11A lands the same raw shape into BigQuery.

That gives you two complementary outputs from the same source family:

- a streaming-derived aggregate table for the first event-processing demo
- a `dlt`-landed raw table for the first warehouse-ingestion demo

## Command Order

### Step 5: Normalize the source file

```bash
uv run python -m src.ingestion.download_day_ahead
uv run python -m src.ingestion.normalize_day_ahead
```

### Step 8 and Step 9: Run and validate the local streaming path

```bash
docker compose -f ops/docker/compose.local.yml up -d
bash ops/scripts/fetch_flink_jars.sh
.venv-flink/bin/python src/streaming/hourly_lmp_job.py --init-postgres-from-host
uv run python -m src.replay.replay_day_ahead \
--input-path data/normalized/WW_DALMP_ISO_20260317_normalized.csv \
--delay-seconds 0 \
--quiet \
--verify-acks \
--acks-timeout-seconds 10
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c "SELECT COUNT(*) AS row_count FROM stream_hourly_lmp;"
```

### Step 10: Run and validate the local `dlt` raw landing path

```bash
docker compose -f ops/docker/compose.local.yml up -d postgres
until docker compose -f ops/docker/compose.local.yml exec -T postgres \
pg_isready -U postgres -d market_data >/dev/null 2>&1; do sleep 1; done
uv sync
uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw \
--destination postgres \
--destination-dsn postgresql://postgres:postgres@localhost:5432/market_data \
--write-disposition replace
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c 'SELECT COUNT(*) AS row_count FROM "iso_ne_raw"."day_ahead_hourly_lmp_raw";'
```

### Step 10 Follow-Up: Safe append self-test

```bash
uv run python -m src.ingestion.download_day_ahead --report-date 20260318

uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw_append_test \
--destination postgres \
--destination-dsn postgresql://postgres:postgres@localhost:5432/market_data \
--write-disposition replace

uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260318.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw_append_test \
--destination postgres \
--destination-dsn postgresql://postgres:postgres@localhost:5432/market_data \
--write-disposition append

docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c 'SELECT source_file, COUNT(*) AS row_count FROM "iso_ne_raw"."day_ahead_hourly_lmp_raw_append_test" GROUP BY source_file ORDER BY source_file;'
```

Expected validation result for this tested flow:

- `WW_DALMP_ISO_20260317.csv` -> `29064`
- `WW_DALMP_ISO_20260318.csv` -> `29064`

### Step 11A: Run and validate the first BigQuery raw landing

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/workspaces/de-capstone/my-creds/de-zoomcamp-485107-3cbafa3d7c94.json

uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw \
--destination bigquery \
--destination-credentials "$GOOGLE_APPLICATION_CREDENTIALS" \
--write-disposition replace
```

Exact CLI-style validation command that was tested successfully in this repo:

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

Expected validation result for the current Step 11A run:

- `row_count=29064`

## Troubleshooting Notes

- If `docker compose -f ops/docker/compose.local.yml up -d postgres` fails with an OCI runtime error such as `container with given ID already exists`, remove the stale container with `docker rm -f docker-postgres-1` and start PostgreSQL again.
- If the Step 10 `dlt` run fails immediately with `connection refused` or `server closed the connection unexpectedly`, wait for `pg_isready` to succeed before rerunning.
- For BigQuery, `src.ingestion.dlt_raw_ingestion.py` now accepts a service-account file path and reads the JSON before passing credentials into `dlt`.
- The warning that `google-cloud-bigquery-storage` is not installed is non-blocking for this step.

## Shutdown And Cost Control

- Stop only PostgreSQL if you only started the Step 10 raw-landing slice:

```bash
docker compose -f ops/docker/compose.local.yml stop postgres
```

- Stop the full local streaming stack if you started Redpanda, Flink, and related services:

```bash
docker compose -f ops/docker/compose.local.yml down
```

- Remove the compose-managed containers, network, and anonymous volumes if you want full local cleanup:

```bash
docker compose -f ops/docker/compose.local.yml down -v
```

- Local Docker services do not incur cloud charges, but they continue consuming local CPU, memory, and disk while running.
- BigQuery does incur cloud cost through storage and query processing, so avoid unnecessary reruns once validation is complete.

## Reviewer Notes

If you are reading this before implementation exists, the important point is that the repo is being organized so another person can reproduce the build-out without rediscovering the architecture, dataset assumptions, or local workflow.

If you are reading this after implementation starts, begin with `plan.md` and compare the executed steps against the documented procedure.
