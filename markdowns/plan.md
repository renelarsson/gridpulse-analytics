# de-capstone Plan
---
## Purpose

This file is the procedural manual for building the capstone from its current documentation-first state into a runnable local-first implementation.

It is intended to answer three questions in sequence:

1. what are we building
2. why are we building it this way
3. how should we execute the work, step by step, without guessing

This repository is the capstone project root. The folders `data-engineering-zoomcamp/` and `homework/` remain reference material only.

---
## Current Implementation Decision

The first implementation pass will use historical ISO-NE day-ahead hourly LMP data only.

Why this is the right cut (a small scoped piece of work) now:

1. it is reachable from the current environment
2. it gives a stable first schema to normalize
3. it lets the project start developing immediately
4. it keeps the final architecture streaming-first while avoiding early dependence on blocked anonymous live endpoints

Real-time hourly and five-minute feeds remain part of the target architecture, but they are not part of the first coding pass.

---
## Approved Technical Direction

- cloud: GCP
- dashboard: Streamlit
- ingestion: dlt
- streaming posture: streaming-first
- Python baseline: 3.12
- warehouse: BigQuery
- transformations: dbt
- infrastructure: Terraform
- orchestration for non-streaming tasks: Kestra
- stream stack: Redpanda plus PyFlink
- local Python workflow: `uv`
- local service runner: Docker Compose

---
## Working Outcome For The First Demo

The first end-to-end demo should prove this path:

1. download one or more historical ISO-NE day-ahead hourly files
2. normalize them into a canonical event schema
3. replay those events into Redpanda
4. run one PyFlink aggregation
5. land the result in PostgreSQL
6. document the commands, outputs, and validation checks clearly enough to repeat

That is the narrowest slice (a small scoped piece of work) that proves the capstone direction without overbuilding.

## Current Verified Status

The first local streaming demo is now verified.

- replay validation completed with `input_rows=29064`, `sent=29064`, and `acked=29064`
- the running Flink job showed non-zero `Records Sent` and `Records Received` during replay
- PostgreSQL sink validation returned `26642` rows in `stream_hourly_lmp`
- sample query output confirmed interpretable hourly aggregates by `location_name`

---
## Operating Principles

### Teach-first

Before each implementation step, record:

- what is being done
- why it matters
- which files are involved
- which commands are expected to run
- what success looks like

### Local-first

Start locally before adding GCP, Terraform, Kestra, dbt, or Streamlit. Local unknowns should be resolved before cloud unknowns are introduced.

### Narrow first pass

Do not widen the scope to real-time hourly, five-minute, or multi-source enrichment until the day-ahead-only path is stable.

---
## Sequential Build Manual

---
### Step 0: Confirm the repo boundary

**What:** Confirm that implementation work belongs under the repository root and not inside the course or homework folders.

**Why:** This prevents capstone code from being mixed with reference material.

**How:** Use the root for all future project code and docs.

- Create the implementation folders:

```bash
# src/replay contains code for reprocessing historical historical ISO-NE data
mkdir -p src/ingestion src/replay src/streaming src/schema
mkdir -p infra/terraform orchestration/kestra transform/dbt
# ops/ folders are used for infrastructure and deployment-related files
mkdir -p apps/streamlit ops/docker ops/scripts
mkdir -p tests/unit tests/integration data/raw data/normalized
```
The term "replay" is used because the process involves re-sending historical or pre-recorded events to simulate real-time streaming. This is common in event-driven systems where:

- Replay emphasizes the temporal aspect, mimicking the original event sequence.
- Publish is more generic and doesn't convey the temporal simulation.

**Success:** The repo has a clear separation between capstone code and reference material.

### Step 1: Verify local prerequisites

**What:** Verify the baseline host tooling before creating project code.

**Why:** It is cheaper to catch missing host dependencies before debugging Python packages, containers, or streaming jobs.

**How:**
- Run these checks:

```bash
python3.12 --version
uv --version
docker --version
docker compose version
git --version
```

- Install missing host dependencies:

```sh
pip install uv
uv
```

- Run these checks when the cloud phase begins:

```bash
gcloud --version
terraform --version
```

**Success:** The machine has the minimum toolchain required for the first local milestone.

---
### Step 2: Initialize the Python project

**What:** Create a Python 3.12 project managed with `uv`.

**Why:** The project needs one reproducible environment for parsing, replay, validation, and orchestration helpers.

**How:** 
- When implementation starts, initialize the environment:

```bash
# Creates .python-version, .python-version, and pyproject.toml files
uv init --python 3.12
# Creates .venv foler
uv venv --python 3.12 .venv
source .venv/bin/activate
```

-  Then add the first expected dependency groups to the environment. The exact list should be adjusted only after the first commands are validated:

```bash
# Creates uv.lock file with psycopg, a PostgreSQL adapter for Python
uv add dlt pandas pydantic requests psycopg[binary] kafka-python
# Only includ tests in dev with ruff, a Python linter and code formatter
uv add --dev pytest ruff
```

- Do not add cloud or dashboard dependencies yet unless they are required for the first local slice (a small scoped piece of work).

**Success:** The repo has one working Python environment and a dependency file that can be recreated by another machine.

---
### Step 3: Lock the first sample source

**What:** Choose one day-ahead hourly historical ISO-NE CSV as the first canonical sample.

**Why:** Every downstream file, schema, and replay decision depends on one known-good source example.

**How:** 

- Record and test the sample URL:

```bash
curl -I -L --max-redirs 5 \
'https://www.iso-ne.com/histRpts/da-lmp/WW_DALMP_ISO_20260317.csv'
```
**Note:** *`curl` transfers data from or to a server. `-I` fetches only the HTTP headers of the response, not the body. This is useful for checking metadata about the file (e.g., content type, size, etc.). `-L` follows redirects if the URL is redirected to another location. This ensures you reach the final destination URL. `--max-redirs 5` limits the number of redirects to follow to 5. This prevents infinite loops in case of misconfigured redirects. The file (~ 2.4 MB) contains **Day-Ahead Locational Marginal Pricing** (Day-Ahead LMP) data for the ISO New England electricity market. **LMP** is the price of electricity at specific locations (nodes) in the grid, determined by supply and demand. It includes an **Energy Component**, a **Congestion Component**, and a **Marginal Loss Component**. The **Energy Component** is the cost of generating electricity. The **Congestion Component** is the cost of delivering electricity through congested transmission lines. The **Marginal Loss Component** is the cost of energy lost during transmission. The **Day-Ahead Market** is a market where electricity prices are determined one day in advance based on forecasts of supply and demand. The data in this file represents the prices and other related metrics for March 17, 2026.*

* Download one sample into the data/raw folder:
    - **Make sure `Cache-Control: no-cache` in the output:** LMP reports are time-sensitive and may be updated or corrected after initial publication. By enforcing no-cache, ISO-NE ensures clients always check for the latest version.

```bash
curl -L \
'https://www.iso-ne.com/histRpts/da-lmp/WW_DALMP_ISO_20260317.csv' \
-o data/raw/WW_DALMP_ISO_20260317.csv
```

```
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 2418k  100 2418k    0     0  16.1M      0 --:--:-- --:--:-- --:--:-- 16.1M

```
- Inspect the first lines of the raw file to confirm the report structure:

```bash
head -n 7 data/raw/WW_DALMP_ISO_20260317.csv
```
```
"C","Day-Ahead Energy Market Hourly LMP Report"
"C","Filename: WW_DALMP_ISO_20260317.csv"
"C","Report for: 03/17/2026 - 03/17/2026"
"C","Report generated: 03/16/2026 13:07:54 EDT"
"H","Date","Hour Ending","Location ID","Location Name","Location Type","Locational Marginal Price","Energy Component","Congestion Component","Marginal Loss Component"
"H","Date","HE","String","String","String","Number","Number","Number","Number"
"D","03/17/2026","01","321","UN.FRNKLNSQ13.810CC","NETWORK NODE",27.93,27.75,0.0,0.18
```

**Success:** The repo has one reproducibly downloadable source file and a confirmed raw structure with metadata rows, a field-name row, a field-type row, and data rows.

---
### Step 4: Define the normalized schema

**What:** Map the raw day-ahead CSV columns to one canonical event schema. The `Canonical Event Schema` is the final, standardized structure used across a project to represent data consistently. It ensures that all downstream systems (e.g., storage, analytics, streaming) can rely on a single, unambiguous format. The schema typically includes `Field Names` that are stable and meaningful. `Data Types`, `Constraints`, and any transformations or mappings applied to raw data.

**Why:** Replay, streaming, storage, and analytics all become simpler once raw vendor names are converted into stable project names.

**How:** Create the initial event schema to document:

1. raw column names
2. normalized field names
3. timestamp construction logic from `Date` and `Hour Ending`
4. timezone assumptions

- Create the schema:
```bash
touch src/schema/iso_ne_day_ahead_schema.py
```
- Use these initial events as aliases for above column headers:
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

- Add the `market_timestamp_utc` construction logic in [src/schema/iso_ne_day_ahead_schema.py](../src/schema/iso_ne_day_ahead_schema.py).
    - `market_timestamp_utc` combines `Date` and `Hour Ending` using the ISO-NE source date format `MM/DD/YYYY`.
    - Interpret the source timestamp in New England market time using `America/New_York`.
    - Convert the result to UTC for the canonical event timestamp.
- See Step 5 below regarding `market_type`, `source_file`, and `ingest_run_id`.

**Success:** One raw row can be converted into one canonical project event without ambiguity.

---
### Step 5: Create the first ingestion and normalization scripts

**What:** Create the smallest set of scripts needed to download and normalize the chosen sample.

**Why:** The project should not jump directly into dlt, Redpanda, or PyFlink without first proving the raw file can be converted into a usable event stream.

**How:** Create these initial script targets:
```bash
touch src/ingestion/download_day_ahead.py
touch src/ingestion/normalize_day_ahead.py
```

- Responsibilities:

    - [download_day_ahead.py](../src/ingestion/download_day_ahead.py): Fetches the historical day-ahead market file and saves it to the `data/raw/` directory. Status: implemented.
    - [normalize_day_ahead.py](../src/ingestion/normalize_day_ahead.py): Reads the raw file, skips ISO-NE metadata and the field-type row, keeps only data rows where the leading record type is `D`, normalizes fields, and writes a normalized CSV to the `data/normalized/` directory. Status: implemented.
    - `market_type`: Add as a static value during normalization. Status: implemented.
    - `source_file`: Populate during normalization from the raw input file path. Status: implemented.
    - `ingest_run_id`: Generate once per normalization run as a UUID and assign it to each normalized row from that run. Status: implemented.

- For the first sample file, the expected normalized output path is:

```bash
data/normalized/WW_DALMP_ISO_20260317_normalized.csv
```

- Expected normalization command pattern:

```bash
uv run python -m src.ingestion.download_day_ahead
uv run python -m src.ingestion.normalize_day_ahead
```

- Optional refinements after Step 5 validation:
    - Replace hardcoded example paths with CLI arguments. Status: planned.
    - Enforce stable output dtypes for integers, numerics, and timestamps. Status: planned.
    - Add validation for malformed or missing rows before writing normalized output. Status: planned.

**Success:** The repo can move from raw source file to normalized local dataset repeatably.

---
### Step 6: Stand up the local containers

**What:** Create the local service stack for streaming and sink validation.

**Why:** 

Replay and PyFlink validation need a known local runtime before any cloud work begins.

In this plan, a `local service stack` means the set of cooperating infrastructure services that make the first streaming demo possible.

- **Replay** in `src/replay/replay_day_ahead.py` is the application code that will publish normalized events (see Step 7).
- **PyFlink** in `src/streaming/hourly_lmp_job.py` is the stream-processing framework the application code will use (see Step 8).
    - Neither one is the runtime by itself. Both need external services around them to run predictably.

What a `known local runtime` means here:

- **Redpanda** is reachable at a known hostname and port.
- **PostgreSQL** is reachable at a known hostname and port.
- **Flink JobManager** and **TaskManager** are running in their expected roles.
    - The same service names, versions, and connection settings are used every time.

What `validation` means at this stage:

- **validate replay**: confirm the replay code can connect to Redpanda and publish the expected number of events
- **validate PyFlink**: confirm the Flink job can start, consume those events, process them, and write output to PostgreSQL

The `required local services` for this milestone are:

1. `Redpanda`
    - **role**: event broker
    - **why it is needed**: replay publishes events into Redpanda and PyFlink reads them back from a topic (stream)
2. `PostgreSQL`
    - **role**: validation sink
    - **why it is needed**: PyFlink writes aggregate results somewhere queryable so the first demo can be inspected
3. `Flink JobManager`
    - **role**: job coordinator
    - **why it is needed**: it accepts the streaming job, manages scheduling, and coordinates execution
4. `Flink TaskManager`
    - **role**: execution worker
    - **why it is needed**: it runs the actual stream-processing tasks assigned by the JobManager

How these services work together in the first demo:

1. normalization produces canonical day-ahead records
2. replay sends those records to Redpanda
3. PyFlink reads those events from Redpanda
4. PyFlink computes the first aggregation
5. PyFlink writes the results to PostgreSQL
6. PostgreSQL is queried to verify that the output is correct

**How:** Create the container area:

```bash
touch ops/docker/compose.local.yml
```

- [compose.local.yml](../ops/docker/compose.local.yml) is used instead of the generic `docker-compose.yml` name to make it explicit that this file is for the local-only runtime. That leaves room for future files such as `compose.demo.yml` or `compose.cloud.yml` if needed.

- The first compose file will include only the services required for the first milestone:

1. Redpanda
2. PostgreSQL
3. Flink JobManager
4. Flink TaskManager

- Start the stack with:

```bash
docker compose -f ops/docker/compose.local.yml up -d
docker compose -f ops/docker/compose.local.yml ps
```

- Stop it with:

```bash
docker compose -f ops/docker/compose.local.yml down
```

`-f` tells Docker Compose which file to use. It is needed here because the compose file is stored at `ops/docker/compose.local.yml` instead of using the default filename in the current directory.

`docker compose` is the current Docker CLI form of Compose. Older material may use `docker-compose`, which is the legacy standalone command.

**Success:** The required local services start, remain reachable, and can be restarted repeatably.

---
### Step 7: Implement deterministic replay

**What:** Replay the normalized day-ahead events into Redpanda in a stable, documented order.

**Why:** This converts static historical data into an event stream that can drive the first streaming job.

**How:** 
- Create the replay module:

```bash
touch src/replay/replay_day_ahead.py
```

- Document these design choices:

1. Topic Name:
    - The Kafka topic where events are published (defined in the current implementation as `DEFAULT_TOPIC_NAME = "day_ahead_events"` in `replay_day_ahead.py`). Status: implemented.
        - This ensures clarity about where the replayed events are sent.

2. Event Ordering Field:
    - The replay sorts events by `market_timestamp_utc`, then uses `location_id` and `location_name` as deterministic tie-breakers. Status: implemented.
        - This is explicitly defined in the current implementation and keeps replay order stable across repeated runs of the same input file.

3. Replay Rate or Batch Strategy:
    - The current implementation shapes the stream during replay by sending events one-by-one rather than in batches. One-by-one is simplest; batching can be much faster but changes load characteristics and failure semantics. Status: implemented.
    - `REPLAY_DELAY_SECONDS` is currently set to `0.031` seconds, which was chosen to reduce a full-file replay from more than 8 hours to roughly 15 minutes. Status: implemented.
    - The replay script now accepts CLI arguments so the operator can choose the input file, delay, broker, and topic at runtime without editing source code. Status: implemented.

4. Idempotency or Rerun Assumptions:
    - Replay order is deterministic for the same input file, but rerunning the script republishes the same events. Status: implemented.
        - In other words, the current replay behavior is repeatable, but not idempotent at the broker level. Duplicate events should be treated as acceptable for the first local demo unless downstream deduplication is added later.

These details help ensure that the replay process is predictable, repeatable, and well-understood by anyone working on or reviewing the project.

- Replay reads the normalized CSV produced in Step 5 rather than a separate JSON export. Status: implemented. For the first sample, that handoff file is:

```bash
data/normalized/WW_DALMP_ISO_20260317_normalized.csv
```

- For quicker local testing, a smaller file can be created from that canonical normalized output:

```bash
head -n 1001 data/normalized/WW_DALMP_ISO_20260317_normalized.csv > data/normalized/WW_DALMP_ISO_20260317_normalized_small.csv
```

- Expected run pattern:

```bash
uv run python -m src.replay.replay_day_ahead --quiet
```

- Adjusting the replay delay:

The original replay delay of 1 second per row resulted in a total duration of more than 8 hours for 29,065 rows, which was too slow for practical iteration.

To keep replay usable during local development:

1. The default replay delay was reduced to `0.031` seconds.
2. A 1,000-row small-file variant was created for quick validation runs.
3. The replay script now prints total elapsed time and sent-event count so the operator can confirm the runtime of each replay.

- Example CLI runs:

All example runs use `--quiet` to avoid printing one line per event. Omit `--quiet` if you want to see the per-event `published ...` logs.

```bash
# Replay the canonical normalized file with the default ~15 minute delay
uv run python -m src.replay.replay_day_ahead \
--input-path data/normalized/WW_DALMP_ISO_20260317_normalized.csv \
--delay-seconds 0.031 \
--quiet

# Replay the 1,000-row small file for a short local validation run
uv run python -m src.replay.replay_day_ahead \
--input-path data/normalized/WW_DALMP_ISO_20260317_normalized_small.csv \
--delay-seconds 0.031 \
--quiet
```

- Making Step 7 measurable (input rows vs broker-acked messages):

By default, the replay script reports how many input rows it loaded and how many `send()` calls it made. For an exact end-to-end check that the broker acknowledged every message, run with `--verify-acks`. In that mode, the producer waits for an acknowledgement for each record and the script will fail if the acknowledged count does not match the input row count.

```bash
# Verify that every input row was acknowledged by the broker
uv run python -m src.replay.replay_day_ahead \
--input-path data/normalized/WW_DALMP_ISO_20260317_normalized_small.csv \
--delay-seconds 0.031 \
--quiet \
--verify-acks \
--acks-timeout-seconds 10
```

**Success:** Replay can load the normalized CSV, publish events to Redpanda in a stable order, and complete within a practical local testing window. Exact input-versus-output event count verification is still a useful follow-up enhancement.

---
### Step 8: Create the first PyFlink job

**What:** Build one small PyFlink job that reads replayed Kafka events and writes one hourly summary per `location_name` into PostgreSQL.

- This step is intentionally narrow:
    - one input stream: Kafka topic `day_ahead_events`
    - one grouping key: `location_name`
    - one time rule: hourly tumbling windows
    - one sink table: `stream_hourly_lmp`
- The business question for this step is: what were the average and maximum `lmp_total` values for each location during each hour?

**Why:** Step 7 proved that events can move into Kafka. Step 8 should prove that Flink can compute a result from those events.

- In plain terms, Step 8 is the first end-to-end processing demo:
    - normalized CSV -> replay script -> Redpanda -> Flink aggregation -> PostgreSQL result table
- This is different from simple message transport, where data only moves from one place to another without being grouped or aggregated.

**Procedure:** Reproduce Step 8 in the following order.

- Prerequisites from earlier steps:
    - Step 2 created the main project environment `.venv` and installed the repo dependencies
    - Step 5 produced the canonical normalized file at `data/normalized/WW_DALMP_ISO_20260317_normalized.csv`
    - Step 6 introduced the local Docker Compose stack in `ops/docker/compose.local.yml`
    - Step 7 created the replay script `src/replay/replay_day_ahead.py`

- Which environment to use when:
    - Use the main project environment for download, normalization, and replay commands
    - Use the dedicated `.venv-flink` environment only for the PyFlink job submission command
    - If you use `uv run`, you usually do not need to activate `.venv` manually because `uv` runs the command in the project environment

- One-time setup for the main project environment from Step 2:

```bash
uv venv --python 3.12 .venv
uv sync
```
The uv tool automatically handles the environment activation going forward.

- If the normalized CSV does not already exist, recreate the Step 5 outputs with the main project environment:

```bash
uv run python -m src.ingestion.download_day_ahead
uv run python -m src.ingestion.normalize_day_ahead
```

- Start the local services from Step 6:

```bash
docker compose -f ops/docker/compose.local.yml up -d
```

This starts prebuilt `Redpanda`, `PostgreSQL`, `Flink JobManager`, and `Flink TaskManager` images. No local image build is required here because `ops/docker/compose.local.yml` references published images directly.

- Download the connector JARs that the PyFlink job requires before it can talk to Kafka and PostgreSQL:

```bash
bash ops/scripts/fetch_flink_jars.sh
```

This places the `Kafka connector`, `JDBC connector`, and `PostgreSQL JDBC driver` under `ops/flink/jars/`. `src/streaming/hourly_lmp_job.py` checks this directory before submitting the job.

- Create the dedicated PyFlink environment once:

```bash
python3.12 -m venv .venv-flink
.venv-flink/bin/pip install apache-flink psycopg[binary]
```

This is a design choice to isolate PyFlink dependencies from the main project environment and avoid conflicts. The main `.venv` remains the default environment for most capstone code
and `.venv-flink` exists only for running the PyFlink job locally.

Use the containerized tools that already come with the Step 6 stack for inspection. For Step 8, the process is:

- Docker Compose starts and keeps Redpanda, PostgreSQL, and Flink running
- `.venv-flink/bin/python` submits the PyFlink job
- `docker compose ... exec redpanda rpk ...` verifies the Kafka topic from inside the Redpanda container
- `docker compose ... exec postgres psql ...` verifies the sink table from inside the PostgreSQL container

- Submit the Step 8 job with the PyFlink environment:

```bash
.venv-flink/bin/python src/streaming/hourly_lmp_job.py --init-postgres-from-host
```

`.venv-flink/bin/python` ensures `pyflink` is available.
`src/streaming/hourly_lmp_job.py` submits the SQL job to the Flink JobManager at `localhost:8081`.
`--init-postgres-from-host` drops and recreates the sink table from the host before the streaming insert starts.

- Verify the submitted job before replaying data:

```bash
curl -s http://localhost:8081/jobs/overview
```
The expected running job name is `insert-into_default_catalog.default_database.stream_hourly_lmp`. The expected state is `RUNNING`. This name comes from the SQL insert target in `src/streaming/hourly_lmp_job.py`: the script executes `INSERT INTO {args.sink_table}` and the default sink table is `stream_hourly_lmp`, so Flink exposes the running insert using that generated name in the REST API and UI.

- Verify the Kafka topic exists before replaying data:

```bash
docker compose -f ops/docker/compose.local.yml exec redpanda rpk topic list
```

The expected topic for Step 8 is `day_ahead_events`.

- Replay the normalized events with the main project environment:

```bash
uv run python -m src.replay.replay_day_ahead \
--input-path data/normalized/WW_DALMP_ISO_20260317_normalized.csv \
--delay-seconds 0 \
--quiet \
--verify-acks \
--acks-timeout-seconds 10
```

Use the full normalized file here, not the 1,000-row small file. The small file only contains one event hour, so it is good for replay testing but not good for proving that hourly windows close and emit output.

**Validation:** Validate the sink output after the replay finishes.

- Confirm the local services are still healthy while validation is running:

```bash
docker compose -f ops/docker/compose.local.yml ps
```

`Redpanda`, `PostgreSQL`, `flink-jobmanager`, and `flink-taskmanager` should all be up. 

- If you want to verify PostgreSQL without a host-installed `psql` client, use the service container:

```bash
docker compose -f ops/docker/compose.local.yml exec -e PGPASSWORD=postgres postgres \
psql -U postgres -d market_data -c "SELECT COUNT(*) AS row_count FROM stream_hourly_lmp;"
```

This verifies the sink using the PostgreSQL client already present in the database container.

- Main inspection query:

```sql
SELECT location_name, window_start, window_end, avg_lmp_total, max_lmp_total, row_count
FROM stream_hourly_lmp
ORDER BY avg_lmp_total DESC
LIMIT 20;
```

This query is the one that shows what the job actually computed. One result row per location per emitted hour.

- A second useful validation query is:

```sql
SELECT COUNT(*) AS row_count
FROM stream_hourly_lmp;
```

This second query does not show the values of the aggregates. It only confirms that rows were written to the sink and gives a quick size check.

- Working validation result for the current local stack:
    - the job submitted successfully to the Flink JobManager at `localhost:8081`
    - replaying the full normalized file with `--delay-seconds 0 --quiet --verify-acks` produced `input_rows=29064 sent=29064 acked=29064`
    - after that replay, `SELECT COUNT(*) FROM stream_hourly_lmp;` returned `26642`
    - the Flink UI showed non-zero `Records Sent` and `Records Received` values for the running source and sink operators during replay

**Notes:** These notes explain why the Step 8 procedure is set up this way.

- What the job computes:
    - it groups rows by `location_name`
    - it groups time using a `60` minute tumbling window over event time
    - a tumbling window is a fixed, non-overlapping time bucket such as `00:00-01:00` or `01:00-02:00`
    - for each location and hour, it writes:
        - `avg_lmp_total`
        - `max_lmp_total`
        - `row_count`

- Why the event-time field matters:
    - use `market_timestamp_utc` from the normalized CSV as the event-time source
    - event time means when the market event actually happened, not when the replay script happened to publish the record
    - this keeps the hourly aggregation aligned with business time instead of machine processing time

- Event-time parsing used by the job:

```sql
event_time AS TO_TIMESTAMP(
  SUBSTRING(market_timestamp_utc, 1, 19),
  'yyyy-MM-dd HH:mm:ss'
)
```

`SUBSTRING(..., 1, 19)` removes the trailing `+00:00` timezone offset so the value matches the format expected by `TO_TIMESTAMP`. Here, offset means the timezone difference from UTC; `+00:00` means the timestamp is already in UTC.

- Window definition:
    - use a `60` minute tumbling window over `event_time`
    - use a `5` second watermark tolerance
    - the watermark is Flink's estimate of how far event time has advanced
    - the `5` second tolerance gives slightly late records a short chance to arrive before Flink finalizes a window

- Parallelism note that matters here:
    - the Kafka `day_ahead_events` topic currently has `1` partition, so the Flink job should also run with `parallelism.default = 1`
    - otherwise an idle source subtask can hold back watermark progression and prevent the tumbling windows from emitting results

- Sink table shape:
    - this is the schema of the PostgreSQL table that stores the Flink output
    - it defines what columns are written and what each result row looks like

```sql
CREATE TABLE stream_hourly_lmp (
  location_name TEXT NOT NULL,
  window_start TIMESTAMP NOT NULL,
  window_end TIMESTAMP NOT NULL,
  avg_lmp_total DOUBLE PRECISION,
  max_lmp_total DOUBLE PRECISION,
  row_count BIGINT NOT NULL
);
```

- Checklist to document for Step 8:
    - the event-time field
    - the window definition
    - the sink table shape
    - the validation query used to inspect output
    - which environment runs which command
    - the exact command order required to reproduce the step

- How the plan maps to the actual source file `src/streaming/hourly_lmp_job.py`:
    - `load_pyflink_table()` lazy-imports `pyflink`, which is why only the job command needs `.venv-flink`
    - `require_jars()` ensures the connector JARs exist before submission
    - `init_postgres_sink_table()` drops and recreates `stream_hourly_lmp` from the host connection
    - `source_ddl` defines the Kafka source, computed `event_time`, and watermark
    - `sink_ddl` defines the JDBC sink into PostgreSQL
    - `insert_sql` defines the tumbling-window aggregation and writes the output rows

- Full flow in words:
    - the Docker Compose services start first and stay running in the background
    - the PyFlink job is submitted next and then waits for records on Kafka
    - the Flink UI or REST endpoint is checked to confirm that the submitted job is actually running
    - the Kafka topic is checked before replay so Step 8 does not fail on a missing source topic
    - the replay script publishes normalized records into Redpanda
    - Flink reads those records, groups them by event-time hour and location, and writes aggregates to PostgreSQL
    - PostgreSQL is queried last to inspect whether Step 8 produced interpretable output

- Troubleshooting note from the local runtime validation:
    - if a Redpanda client reports a DNS resolution error for `redpanda`, the problem is usually the broker advertised address relative to where the client is running, not the Flink job submission command itself
    - inside the Compose network, `redpanda:9092` is the expected broker address
    - host-side package installation errors such as `dpkg` locks, `debconf` locks, or `invoke-rc.d` warnings are separate from the Step 8 data-path logic and should be debugged as host package-management issues

**Success:** The job runs successfully and writes interpretable aggregate rows to PostgreSQL.

---
### Step 9: Validate the output in PostgreSQL

**What:** Confirm that the stream result lands in a queryable sink.

**Why:** A working sink is the first proof that the local demo produces inspectable business output.

**How:** 

- Use the PostgreSQL client inside the database container so the validation stays on the current process:

```bash
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c "SELECT COUNT(*) AS row_count FROM stream_hourly_lmp;"
```

For the current validated run, this query returned `26642`.

- Then inspect representative rows:

```sql
SELECT location_name, window_start, window_end, avg_lmp_total, max_lmp_total, row_count
FROM stream_hourly_lmp
ORDER BY avg_lmp_total DESC
LIMIT 20;
```

For the current validated run, the top rows were emitted for the `2026-03-17 11:00:00` to `2026-03-17 12:00:00` window and included populated `avg_lmp_total`, `max_lmp_total`, and `row_count` values.

The expected result shape is:

- one row per `location_name` per emitted hourly window
- `window_start` and `window_end` showing the Flink tumbling-window bounds
- `avg_lmp_total` and `max_lmp_total` populated with numeric aggregates
- `row_count` showing how many source rows contributed to that location-window result

**Additional Notes:**

- **Validation Queries:**
  - Row count validation ensures the sink table is populated.
  - Aggregate inspection confirms the correctness of the tumbling window logic.
- **Flink Metrics:**
  - During replay, the Flink UI showed non-zero `Records Sent` and `Records Received` values for the source and sink operators.
- **Replay Verification:**
  - Replay metrics confirmed `input_rows=29064`, `sent=29064`, and `acked=29064`.

**Success:** The sink answers at least one of the milestone business questions and the validation proves that the first local replay-to-aggregation-to-PostgreSQL slice (a small scoped piece of work) is complete.

---
### Step 10: Introduce dlt for the raw and warehouse path

**What:** Bring dlt into the project once the local raw-to-normalized path (the `CSV -> dlt load -> warehouse table` data flow) is clear.

**Why:** dlt should formalize ingestion, i.e. know the source structure and assumptions clearly, before dlt automates loading.

**Procedure:** Reproduce Step 10 in the following order.

- Prerequisites from earlier steps:
    - Step 2 created the main project environment `.venv` and installed `dlt`
    - Step 3 defined the first raw historical sample at `data/raw/WW_DALMP_ISO_20260317.csv`
    - Step 6 introduced the local PostgreSQL service in `ops/docker/compose.local.yml`
    - Step 5 already proved that the raw file structure is understood outside of `dlt` (the raw file was downloaded, metadata and type rows were skipped, `D` rows were isolated, and a normalized file was produced successfully)

- Step 10 keeps the first `dlt` slice intentionally narrow:
    - one entry point: `src/ingestion/dlt_raw_ingestion.py`
        - the executed script that starts Step 10
    - one source file: `data/raw/WW_DALMP_ISO_20260317.csv`
    - one destination: the local PostgreSQL database already used in the Docker Compose stack
    - one table: `iso_ne_raw.day_ahead_hourly_lmp_raw`

- Why this is the right cut (a small scoped piece of work):
    - it adds `dlt` without changing the validated source file format
    - it keeps the first warehouse-style load local and easy to inspect
    - it creates one repeatable ingestion command before BigQuery, dbt, or orchestration are introduced

- Start only the database service needed for this slice:

```bash
docker compose -f ops/docker/compose.local.yml up -d postgres
```

This is enough for Step 10 because the first `dlt` slice does not need Redpanda or Flink. The goal here is raw landing (loading source data into storage with minimal transformation), not streaming.

- Wait until PostgreSQL is actually ready before running the `dlt` command:

```bash
until docker compose -f ops/docker/compose.local.yml exec -T postgres \
pg_isready -U postgres -d market_data >/dev/null 2>&1; do sleep 1; done
```

This avoids a startup race where the container is up but the database process is not yet ready to accept client connections.

- Ensure the main project environment includes the PostgreSQL destination extra (optional dependencies for a specific feature) for `dlt`:

```bash
uv sync
```

The project dependency set for Step 10 should include `dlt[postgres]`, not just the base `dlt` package (i.e. the packages needed for the Postgres destination). The base package is enough to define the pipeline, but the PostgreSQL destination requires the destination-specific extra dependencies before the load can run.

- If the raw source file is not already present, recreate it with the main project environment:

```bash
uv run python -m src.ingestion.download_day_ahead
```

This keeps the Step 10 source aligned with the file already validated in the earlier steps.

- Run the `dlt` pipeline entry point:

```bash
uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw \
--destination postgres \
--destination-dsn postgresql://postgres:postgres@localhost:5432/market_data \
--write-disposition replace
```

What this command does:

- `uv run` executes the pipeline in the main project environment from Step 2
- `src.ingestion.dlt_raw_ingestion` reads the raw ISO-NE CSV directly
- `--dataset-name iso_ne_raw` creates a dedicated PostgreSQL schema for this first raw landing slice
- `--table-name day_ahead_hourly_lmp_raw` makes the table purpose explicit
- `--destination postgres` keeps the pipeline shape aligned with a later warehouse destination while staying local-first now
- `--destination-dsn ...` points `dlt` at the local PostgreSQL service already defined in `ops/docker/compose.local.yml`
- `--write-disposition replace` makes the first demo rerunnable without manual cleanup between tests

- Add the first append-mode backfill slice only after the single-file `replace` run is already working.

- If you want the safest self-test on a clean table, create the test table first with `replace`, then append the second file:

```bash
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
```

This two-step self-test is more robust than dropping the table and immediately rerunning a single append-only command with the same pipeline state.

- If the table already exists and you want a single-command multi-file backfill, this works as expected:

```bash
uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--input-path data/raw/WW_DALMP_ISO_20260318.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw \
--destination postgres \
--destination-dsn postgresql://postgres:postgres@localhost:5432/market_data \
--write-disposition append
```

What this append-mode backfill adds:

- repeated `--input-path` flags let one run process multiple raw files in sequence
- `--write-disposition append` keeps the already loaded rows and adds the next files behind them
- `source_file` remains populated per row, so the loaded table can still be filtered back to each raw report after the backfill
- this is the right next local warehouse step before moving the same shape into BigQuery

- What the Step 10 code preserves and what it changes:
    - it preserves the raw data rows from the source CSV instead of loading normalized events
    - it skips the report metadata rows and the field-type row because those rows are report framing, not tabular market records
    - it keeps the vendor field values as raw strings in the destination table
    - it renames the columns to SQL-friendly snake_case so the raw landing table is easier to query locally
    - it adds `source_file` and `source_row_number` so each loaded row can be traced back to the original report

- Validate that `dlt` wrote rows into PostgreSQL:

```bash
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c 'SELECT COUNT(*) AS row_count FROM "iso_ne_raw"."day_ahead_hourly_lmp_raw";'
```

This is the Step 10 row-count check. It answers the narrow question for this milestone: did the first `dlt` raw load land rows into a queryable local table?

- For append-mode backfill validation, confirm both total rows and per-file contribution:

```bash
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c 'SELECT source_file, COUNT(*) AS row_count FROM "iso_ne_raw"."day_ahead_hourly_lmp_raw" GROUP BY source_file ORDER BY source_file;'
```

This query is the practical append-mode check because it verifies that multiple source files contributed rows instead of silently replacing one another.

- A second useful inspection query is:

```bash
docker compose -f ops/docker/compose.local.yml exec -T postgres \
psql -U postgres -d market_data -c 'SELECT market_date, hour_ending, location_id, location_name, locational_marginal_price, source_file FROM "iso_ne_raw"."day_ahead_hourly_lmp_raw" ORDER BY source_row_number::int LIMIT 10;'
```

This confirms that the loaded table still looks like the source report and that the data is inspectable before any downstream normalization or transformation layers are applied.

- Working validation result for the current local Step 10 run:
    - running `src.ingestion.dlt_raw_ingestion` against `data/raw/WW_DALMP_ISO_20260317.csv` completed successfully after syncing the environment with the PostgreSQL `dlt` extra installed
    - `SELECT COUNT(*) AS row_count FROM "iso_ne_raw"."day_ahead_hourly_lmp_raw";` returned `29064`
    - rerunning the same command with `--write-disposition replace` completed successfully again and kept the table at `29064` rows, which confirms that the first Step 10 demo is rerunnable without manual cleanup
    - a two-file append-mode validation run into `iso_ne_raw.day_ahead_hourly_lmp_raw_append_test` loaded `58128` rows total, split as `29064` rows from `WW_DALMP_ISO_20260317.csv` and `29064` rows from `WW_DALMP_ISO_20260318.csv`

- Record the concrete Step 10 result shape:
    - destination schema: `iso_ne_raw`
    - destination table: `day_ahead_hourly_lmp_raw`
    - expected grain: one row per raw ISO-NE `D` (data row) record from the source CSV

- Notes that matter for this first `dlt` slice:
    - use PostgreSQL first because it is already part of the validated local stack and is easy to inspect with `psql`
    - keep `replace` for the first process run so the command is deterministic
    - switch to `append` later when repeated historical backfills or multi-file loads become the next requirement
    - do not move this step to BigQuery yet; the point here is to validate the `dlt` shape (overall pipeline structure: source and destination type, table layout, and command pattern) locally before cloud configuration is introduced
    - the `psutil dependency is not installed` warning from `dlt` progress logging is optional observability noise, not a Step 10 failure; it only means memory stats are unavailable in the progress output
    - if `docker compose up -d postgres` fails with an OCI runtime error such as `container with given ID already exists`, remove the stopped service container with `docker rm -f docker-postgres-1` and start the service again
    - if `dlt` fails with `connection refused` or `server closed the connection unexpectedly` immediately after container startup, PostgreSQL is usually not ready yet; rerun only after `pg_isready` succeeds

**Success:** Raw ingestion can be rerun without redefining the source contract (the source data structure/meaning: which columns exist, what row types and timestamps mean, and code assumptions), and the first `dlt` command can be demonstrated without depending on Terraform, dbt, Kestra, or Streamlit.

---
### Step 11: Expand to cloud infrastructure
**What:**, **Why:**, **How:**, **Success:**
#### What

Add GCP, Terraform, Kestra, dbt, and Streamlit only after the first local path is stable.

This step expands the warehouse and orchestration path first. It does not replace the local Redpanda and PyFlink path from Steps 6 to 9.

#### Why

These tools should extend a working base, not be used to discover the base requirements.

The project has two related but different tracks now:

1. historical and warehouse track:
    - raw ISO-NE files
    - `dlt`
    - PostgreSQL first, then BigQuery
    - dbt, Kestra, and Streamlit later on top of warehouse tables
2. streaming and real-time processing track:
    - normalized events
    - Redpanda
    - PyFlink
    - PostgreSQL today as the first inspectable sink

They should converge at shared business definitions and warehouse-ready outputs, not by forcing `dlt` to sit inside the first Redpanda to Flink processing loop.

#### How

Expansion order:

1. Terraform for GCS, BigQuery, service accounts, and IAM
2. dlt raw landing into GCS and BigQuery
3. dbt staging and marts in BigQuery
4. Kestra flows for non-streaming scheduled work
5. Streamlit dashboard on top of stable marts

The first Step 11 cloud slice should stay as close as possible to the already validated Step 10 shape:

1. keep the same entry point: `src/ingestion/dlt_raw_ingestion.py`
2. keep the same dataset and table intent: `iso_ne_raw.day_ahead_hourly_lmp_raw`
3. change only the destination and credentials
4. avoid adding dbt, Kestra, or dashboard work until the first BigQuery landing is proven

#### Step 11A: Warehouse cloud path

This is the direct continuation of the Step 10 warehouse-style raw landing work.

- the append-mode backfill follow-up belongs to Step 10 because it still validates local `dlt` loading behavior
- the BigQuery landing follow-up belongs to Step 11A because it is the first non-local warehouse destination for the same `dlt` shape

How the streaming track fits relative to this order:

1. the Step 10 follow-up can stay local-first for one more slice by adding append-mode backfill for multiple raw files
2. after that, the next non-local `dlt` slice is Step 11 item 2: land the same raw shape into BigQuery
3. the existing Redpanda and PyFlink work remains the streaming proof-of-concept path and does not need to be rewritten around `dlt`
4. if the project later needs cloud streaming, that is a separate follow-on after this step: move the validated Redpanda and PyFlink design to managed cloud infrastructure or a cloud-hosted equivalent while keeping the warehouse track intact
5. the integration point between the two tracks is downstream data modeling and presentation, where historical `dlt` loads and streaming-derived outputs can be compared, joined, or served together

What this means for immediate next steps after Step 10:

1. Add an append-mode backfill procedure for multiple raw files.
2. Land the same `dlt` raw shape into BigQuery as the first Step 11 cloud slice.
3. Add a small README section that links Step 5, Step 8, Step 9, and Step 10 into one end-to-end workflow.

Those are still the right next steps because they reduce uncertainty in the warehouse path without disturbing the already validated local streaming path.

First BigQuery-oriented procedure for Step 11 item 2:

- Ensure the project dependencies include the BigQuery destination extra for `dlt`:

```bash
uv sync
```

- Export the service-account path for the local shell session, or pass the same path directly with `--destination-credentials`:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/gcp-service-account.json
```

The current `src/ingestion/dlt_raw_ingestion.py` entry point accepts the file path directly for BigQuery and reads the service-account JSON before passing credentials to `dlt`.

- Run the same ingestion entry point against BigQuery:

```bash
uv run python -m src.ingestion.dlt_raw_ingestion \
--input-path data/raw/WW_DALMP_ISO_20260317.csv \
--dataset-name iso_ne_raw \
--table-name day_ahead_hourly_lmp_raw \
--destination bigquery \
--destination-credentials "$GOOGLE_APPLICATION_CREDENTIALS" \
--write-disposition replace
```

What changes and what does not in this first cloud slice:

- the source file stays the same
- the raw row contract stays the same
- the table name intent stays the same
- only the destination changes from local PostgreSQL to BigQuery

- Validate the BigQuery landing with the same row-count question in BigQuery SQL:

```sql
SELECT COUNT(*) AS row_count
FROM `iso_ne_raw.day_ahead_hourly_lmp_raw`;
```

- If you want a shell-based validation path from this repo without installing the `bq` CLI, run the BigQuery Python client directly from the project environment:

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

This is the validated CLI-style check for the current environment because `bq` and `gcloud` are not installed here.

- If you prefer the BigQuery web UI, validate the same result in BigQuery Studio:

1. open the `de-zoomcamp-485107` project in BigQuery Studio
2. create a new SQL query tab
3. run the query below:

```sql
SELECT COUNT(*) AS row_count
FROM `de-zoomcamp-485107.iso_ne_raw.day_ahead_hourly_lmp_raw`;
```

4. confirm that the returned count is `29064`

- If you later land the append or backfill test table in BigQuery, use the same per-file validation pattern there:

```sql
SELECT source_file, COUNT(*) AS row_count
FROM `de-zoomcamp-485107.iso_ne_raw.day_ahead_hourly_lmp_raw_append_test`
GROUP BY source_file
ORDER BY source_file;
```

This is the first non-local proof for the warehouse track: the same `dlt` shape that worked locally can land in the target cloud warehouse before dbt, Kestra, or Streamlit are added.

- Working validation result for the current Step 11A run:
    - running `src.ingestion.dlt_raw_ingestion` with destination `bigquery` and the service-account file `my-creds/de-zoomcamp-485107-3cbafa3d7c94.json` completed successfully
    - the validation query `SELECT COUNT(*) AS row_count FROM `iso_ne_raw.day_ahead_hourly_lmp_raw`;` returned `29064`
    - the `google-cloud-bigquery-storage is not installed` warning is optional and does not block the BigQuery load; it only means the Storage API client is unavailable for higher-performance reads

- After Step 10 and Step 11A validation, shut down only what you actually started:
    - local Step 10 only: `docker compose -f ops/docker/compose.local.yml stop postgres`
    - local streaming stack from Steps 8 and 9: `docker compose -f ops/docker/compose.local.yml down`
    - full local cleanup including anonymous volumes: `docker compose -f ops/docker/compose.local.yml down -v`
    - BigQuery does not have a local process to stop, but warehouse storage and repeated queries can incur cloud cost, so avoid unnecessary reruns once validation is complete

#### Step 11B: Later streaming cloud path

This is not the immediate follow-up to Step 10.

- Redpanda and PyFlink were already validated locally in Steps 6 to 9
- the next streaming-cloud decision should come only after the warehouse cloud path is proven and the target modeled outputs are clearer
- when this step is taken later, it should document which managed or hosted equivalents replace the local Redpanda and Flink runtime while preserving the validated event flow
- this later cloud-streaming step should converge with the warehouse path at modeled tables and dashboard inputs, not by forcing `dlt` into the stream-processing loop

#### Success

Cloud and presentation layers are built on top of a proven local-first foundation, while the Redpanda and PyFlink path remains the separate streaming-first branch to extend later rather than being collapsed into the first `dlt` warehouse expansion.

## First Files To Create When Coding Starts

These are the first implementation files the repo should gain:

- `src/schema/iso_ne_day_ahead_schema.py`
- `src/ingestion/download_day_ahead.py`
- `src/ingestion/normalize_day_ahead.py`
- `src/replay/replay_day_ahead.py`
- `src/streaming/hourly_lmp_job.py`
- `ops/docker/compose.local.yml`

This set is intentionally minimal. It is enough to move from source file to normalized data to replay to stream aggregation.

## Validation Standard

The first implementation pass is acceptable only if all of the following are documented:

1. exact source URLs used
2. exact commands run
3. raw headers observed
4. normalized schema used
5. replay row counts
6. stream output validation query
7. open issues and deferred scope

## Explicit Exclusions For The First Coding Pass

- real-time hourly comparison logic
- live anonymous five-minute ingestion
- broad cloud deployment
- full dashboard build
- advanced anomaly detection
- CI/CD hardening before the local commands are stable

## Why This Plan Is Verbose

The purpose of this plan is not to be short. The purpose is to reduce uncertainty when implementation begins.

If a future step feels unclear, the correct action is to add procedure to this file before adding more code.
