# Step 1 To Step 7 Service Flow
* **step-1-to-7-service-flow.md**:
Shows the end-to-end service and artifact flow across the current root README sections, from environment creation to dashboard and Terraform validation.

```mermaid
flowchart LR
    classDef script fill:#f4f1e8,stroke:#6b5f4a,color:#1f1a14,stroke-width:1px;
    classDef artifact fill:#eef6ff,stroke:#326ea8,color:#102234,stroke-width:1px;
    classDef runtime fill:#edf7ed,stroke:#3a7a3a,color:#102510,stroke-width:1px;
    classDef sink fill:#fff1e8,stroke:#b66a2c,color:#341b08,stroke-width:1px;
    classDef infra fill:#f5ecff,stroke:#7356a6,color:#231433,stroke-width:1px;

    subgraph S1[Section 1 - Python environments]
        uv_env[uv + Python 3.12]:::script --> main_env[.venv]:::artifact
        pyflink_env[uv + Python 3.11]:::script --> flink_env[.venv-flink]:::artifact
    end

    subgraph S2[Section 2 - Source preparation]
        iso_source[ISO-NE historical report]:::artifact --> download[src/ingestion/download_day_ahead.py]:::script
        download --> raw_csv[data/raw/*.csv]:::artifact
        raw_csv --> normalize[src/ingestion/normalize_day_ahead.py]:::script
        normalize --> normalized_csv[data/normalized/*_normalized.csv]:::artifact
    end

    subgraph S3[Section 3 - Streaming path]
        compose[ops/docker/compose.local.yml]:::script --> redpanda[Redpanda]:::runtime
        compose --> postgres[PostgreSQL]:::runtime
        compose --> flink[Flink JobManager + TaskManager]:::runtime
        normalized_csv --> replay[src/replay/replay_day_ahead.py]:::script
        replay --> topic[(day_ahead_events)]:::runtime
        redpanda --> topic
        flink_job[src/streaming/hourly_lmp_job.py]:::script --> flink
        topic --> windows[Event-time hourly windows]:::runtime
        flink --> windows
        windows --> stream_sink[stream_hourly_lmp]:::sink
        stream_sink --> postgres
    end

    subgraph S4[Section 4 - Raw warehouse landings]
        raw_csv --> dlt_raw[src/ingestion/dlt_raw_ingestion]:::script
        dlt_raw --> pg_raw[PostgreSQL raw table\niso_ne_raw.day_ahead_hourly_lmp_raw]:::sink
        dlt_raw --> bq_raw[BigQuery raw table\niso_ne_raw.day_ahead_hourly_lmp_raw]:::sink
    end

    subgraph S5[Section 5 - dbt warehouse layer]
        dbt_project[transform/dbt]:::script --> stg[stg_iso_ne_day_ahead_hourly_lmp]:::artifact
        dbt_project --> hourly_mart[mrt_hourly_lmp_by_location]:::artifact
        dbt_project --> daily_mart[mrt_daily_lmp_summary_by_location]:::artifact
        bq_raw --> stg
        stg --> hourly_mart
        stg --> daily_mart
    end

    subgraph S6[Section 6 - Dashboard]
        app[apps/streamlit/app.py]:::script --> dashboard[Streamlit dashboard]:::runtime
        daily_mart --> dashboard
        hourly_mart --> dashboard
    end

    subgraph S7[Section 7 - Infrastructure]
        tf_files[infra/terraform/*.tf]:::infra --> tf_validate[terraform init + validate]:::script
    end

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
```