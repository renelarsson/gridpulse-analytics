import argparse
import importlib
from importlib import metadata
import os
from pathlib import Path
from typing import Any


# Default connection settings assume the local Step 6 Docker Compose stack.
DEFAULT_FLINK_REST_HOST = "localhost"
DEFAULT_FLINK_REST_PORT = 8081

DEFAULT_KAFKA_BOOTSTRAP_SERVERS = "redpanda:9092"
DEFAULT_KAFKA_TOPIC = "day_ahead_events"
DEFAULT_KAFKA_GROUP_ID = "hourly-lmp-job"

DEFAULT_POSTGRES_DB = "market_data"
DEFAULT_POSTGRES_USER = "postgres"
DEFAULT_POSTGRES_PASSWORD = "postgres"

# NOTE: When the Flink job runs inside Docker Compose, it should use the service
# name `postgres` on port 5432. This is distinct from host access via localhost.
DEFAULT_POSTGRES_HOST_FOR_JOB = "postgres"
DEFAULT_POSTGRES_PORT = 5432

DEFAULT_SINK_TABLE = "stream_hourly_lmp"
WATERMARK_SENTINEL_FIELD = "replay_control"
WATERMARK_SENTINEL_VALUE = "watermark_flush"
EXPECTED_FLINK_VERSION = "1.20.1"


# Lazy import so the script can fail with a targeted message if psycopg is missing.
def load_psycopg() -> Any:
    try:
        return importlib.import_module("psycopg")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "psycopg is required to initialize the Postgres sink table. "
            "Install project dependencies in the main .venv."
        ) from exc


    # Lazy import so normal repo work does not require PyFlink until Step 8.
def load_pyflink_table() -> tuple[Any, Any]:
    try:
        pyflink_table = importlib.import_module("pyflink.table")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "pyflink is required to run this job. Recreate .venv-flink with "
            "`uv venv --python 3.11 --seed .venv-flink` and install "
            f"`apache-flink=={EXPECTED_FLINK_VERSION} psycopg[binary]`, then "
            "execute src/streaming/hourly_lmp_job.py from that environment."
        ) from exc

    installed_flink_version = metadata.version("apache-flink")
    if installed_flink_version != EXPECTED_FLINK_VERSION:
        raise RuntimeError(
            "The local Docker stack uses Flink "
            f"{EXPECTED_FLINK_VERSION}, but .venv-flink has apache-flink "
            f"{installed_flink_version}. Recreate .venv-flink with Python 3.11 "
            "and install "
            f"apache-flink=={EXPECTED_FLINK_VERSION} psycopg[binary]."
        )

    return pyflink_table.EnvironmentSettings, pyflink_table.TableEnvironment


# Resolve paths relative to the repo so the script works from any current directory.
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_jars_dir() -> Path:
    return repo_root() / "ops" / "flink" / "jars"


# CLI flags let the same job target local Docker Compose or another compatible stack.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PyFlink job: windowed LMP aggregation from Redpanda to Postgres."
    )

    parser.add_argument("--flink-rest-host", default=DEFAULT_FLINK_REST_HOST)
    parser.add_argument("--flink-rest-port", type=int, default=DEFAULT_FLINK_REST_PORT)

    parser.add_argument(
        "--kafka-bootstrap-servers",
        default=DEFAULT_KAFKA_BOOTSTRAP_SERVERS,
        help="Bootstrap servers as seen from the Flink containers (Docker Compose).",
    )
    parser.add_argument("--topic", default=DEFAULT_KAFKA_TOPIC)
    parser.add_argument("--group-id", default=DEFAULT_KAFKA_GROUP_ID)

    parser.add_argument("--postgres-host", default=DEFAULT_POSTGRES_HOST_FOR_JOB)
    parser.add_argument("--postgres-port", type=int, default=DEFAULT_POSTGRES_PORT)
    parser.add_argument("--postgres-db", default=DEFAULT_POSTGRES_DB)
    parser.add_argument("--postgres-user", default=DEFAULT_POSTGRES_USER)
    parser.add_argument("--postgres-password", default=DEFAULT_POSTGRES_PASSWORD)

    parser.add_argument("--sink-table", default=DEFAULT_SINK_TABLE)

    parser.add_argument(
        "--jars-dir",
        type=Path,
        default=default_jars_dir(),
        help=(
            "Directory containing required Flink connector JARs (Kafka + JDBC) and "
            "the Postgres JDBC driver."
        ),
    )

    parser.add_argument(
        "--window-size-minutes",
        type=int,
        default=60,
        help="Tumbling window size in minutes.",
    )

    parser.add_argument(
        "--init-postgres-from-host",
        action="store_true",
        help=(
            "Create the sink table using a host-reachable Postgres connection. "
            "Uses POSTGRES_HOST_HOSTPORT or defaults to localhost:5432."
        ),
    )

    return parser.parse_args()


# Fail fast if the Kafka and JDBC connector jars are not present for Step 8.
def require_jars(jars_dir: Path) -> list[Path]:
    if not jars_dir.exists():
        raise FileNotFoundError(
            f"JAR directory not found: {jars_dir}. "
            "Run: bash ops/scripts/fetch_flink_jars.sh"
        )

    jar_paths = sorted(jars_dir.glob("*.jar"))
    if not jar_paths:
        raise FileNotFoundError(
            f"No .jar files found in: {jars_dir}. "
            "Run: bash ops/scripts/fetch_flink_jars.sh"
        )

    required_substrings = [
        "flink-sql-connector-kafka",
        "flink-connector-jdbc",
        "postgresql-",
    ]
    missing = [s for s in required_substrings if not any(s in p.name for p in jar_paths)]
    if missing:
        raise FileNotFoundError(
            "Missing required connector JARs in "
            f"{jars_dir}: missing={missing}. "
            "Run: bash ops/scripts/fetch_flink_jars.sh"
        )

    return jar_paths


# Create a clean sink table before submission when running host-side setup.
def init_postgres_sink_table(
    *,
    sink_table: str,
    postgres_db: str,
    postgres_user: str,
    postgres_password: str,
) -> None:
    psycopg = load_psycopg()

    hostport = os.environ.get("POSTGRES_HOST_HOSTPORT", "localhost:5432")
    host, port_str = hostport.split(":", 1)
    port = int(port_str)

    create_sql = f"""
    DROP TABLE IF EXISTS {sink_table};
    CREATE TABLE {sink_table} (
        location_name TEXT NOT NULL,
        window_start TIMESTAMP NOT NULL,
        window_end   TIMESTAMP NOT NULL,
        avg_lmp_total DOUBLE PRECISION,
        max_lmp_total DOUBLE PRECISION,
        row_count BIGINT NOT NULL
    );
    """.strip()

    conninfo = (
        f"host={host} port={port} dbname={postgres_db} "
        f"user={postgres_user} password={postgres_password}"
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)


# Main flow: validate inputs, configure remote Flink, register tables, submit query.
def main() -> None:
    args = parse_args()
    EnvironmentSettings, TableEnvironment = load_pyflink_table()

    # Tumbling windows must have a positive size.
    if args.window_size_minutes <= 0:
        raise ValueError("--window-size-minutes must be > 0")

    # Flink needs the Kafka connector, JDBC connector, and Postgres driver on its classpath.
    jar_paths = require_jars(args.jars_dir)
    pipeline_jars = ";".join(f"file://{p}" for p in jar_paths)

    # Optional host-side table creation is useful before the remote job starts writing.
    if args.init_postgres_from_host:
        init_postgres_sink_table(
            sink_table=args.sink_table,
            postgres_db=args.postgres_db,
            postgres_user=args.postgres_user,
            postgres_password=args.postgres_password,
        )

    # Submit to the remote JobManager exposed by the local Flink container.
    settings = EnvironmentSettings.in_streaming_mode()
    try:
        t_env = TableEnvironment.create(settings)
    except ModuleNotFoundError as exc:
        if exc.name == "pkg_resources":
            raise ModuleNotFoundError(
                "The .venv-flink environment is missing pkg_resources. Install "
                "`setuptools<81` in .venv-flink, then rerun the job."
            ) from exc
        raise

    # Register the remote target and attach the connector jars to the pipeline.
    config = t_env.get_config().get_configuration()
    config.set_string("execution.target", "remote")
    config.set_string("rest.address", args.flink_rest_host)
    config.set_integer("rest.port", args.flink_rest_port)
    config.set_string("pipeline.jars", pipeline_jars)
    config.set_string("parallelism.default", "1")

    # Kafka source DDL.
    # replay_day_ahead.py publishes each normalized CSV row as a flat JSON object,
    # so the Flink source table mirrors those JSON keys directly.
    #
    # We intentionally ingest the timestamp and numeric payload as STRING values at
    # the source boundary because that matches the wire format exactly and avoids
    # rejecting whole records when a single value is malformed. event_time is then
    # derived from market_timestamp_utc for event-time windowing, and lmp_total is
    # cast only inside the aggregation query where Flink needs numeric semantics.
    source_ddl = f"""
    CREATE TABLE day_ahead_events (
      market_timestamp_utc STRING,
      location_name STRING,
      lmp_total STRING,
            replay_control STRING,
            event_time AS TO_TIMESTAMP(
                SUBSTRING(market_timestamp_utc, 1, 19),
                'yyyy-MM-dd HH:mm:ss'
            ),
      WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
    ) WITH (
      'connector' = 'kafka',
      'topic' = '{args.topic}',
      'properties.bootstrap.servers' = '{args.kafka_bootstrap_servers}',
      'properties.group.id' = '{args.group_id}',
      'scan.startup.mode' = 'earliest-offset',
      'format' = 'json',
      'json.ignore-parse-errors' = 'true'
    )
    """.strip()

    sink_url = (
        f"jdbc:postgresql://{args.postgres_host}:{args.postgres_port}/{args.postgres_db}"
    )

    sink_ddl = f"""
    CREATE TABLE {args.sink_table} (
      location_name STRING,
        window_start TIMESTAMP(3),
        window_end TIMESTAMP(3),
      avg_lmp_total DOUBLE,
      max_lmp_total DOUBLE,
      row_count BIGINT
    ) WITH (
      'connector' = 'jdbc',
      'url' = '{sink_url}',
      'table-name' = '{args.sink_table}',
      'username' = '{args.postgres_user}',
      'password' = '{args.postgres_password}',
      'driver' = 'org.postgresql.Driver'
    )
    """.strip()

    t_env.execute_sql(source_ddl)
    t_env.execute_sql(sink_ddl)

    # Keep the SQL interval string derived from the CLI so Step 8 can change window size.
    window_interval = f"INTERVAL '{args.window_size_minutes}' MINUTE"

    # Tumbling-window insert query.
    # TABLE(TUMBLE(...)) turns the unbounded Kafka event stream into fixed-size,
    # non-overlapping event-time windows. Each output row represents one location
    # within one window, carrying the window bounds plus simple aggregate metrics.
    #
    # Because lmp_total arrives as STRING from JSON, the query casts it to DOUBLE
    # at aggregation time for AVG/MAX while COUNT(*) preserves the raw row volume
    # seen in that window.
    insert_sql = f"""
    INSERT INTO {args.sink_table}
    SELECT
      location_name,
      window_start,
      window_end,
      AVG(CAST(lmp_total AS DOUBLE)) AS avg_lmp_total,
      MAX(CAST(lmp_total AS DOUBLE)) AS max_lmp_total,
      COUNT(*) AS row_count
    FROM TABLE(
      TUMBLE(TABLE day_ahead_events, DESCRIPTOR(event_time), {window_interval})
    )
        WHERE replay_control IS NULL OR replay_control <> '{WATERMARK_SENTINEL_VALUE}'
    GROUP BY location_name, window_start, window_end
    """.strip()

    print(
        "starting hourly_lmp_job: "
        f"rest={args.flink_rest_host}:{args.flink_rest_port} "
        f"kafka={args.kafka_bootstrap_servers} topic={args.topic} "
        f"postgres={args.postgres_host}:{args.postgres_port}/{args.postgres_db} "
        f"sink_table={args.sink_table} window_minutes={args.window_size_minutes}"
    )

    # execute_sql submits the streaming insert and returns while the job continues remotely.
    t_env.execute_sql(insert_sql)

    print(
        "job submitted. Use the Flink UI at http://localhost:8081 to confirm it is running."
    )


if __name__ == "__main__":
    main()
