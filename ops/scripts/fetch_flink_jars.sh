#!/usr/bin/env bash
set -euo pipefail

# Downloads Flink connector JARs needed by src/streaming/hourly_lmp_job.py
# Target directory (relative to repo root): ops/flink/jars/

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JARS_DIR="$ROOT_DIR/ops/flink/jars"

FLINK_VERSION_TAG="1.20"
# For Flink 1.20.x, the matching published connector artifacts use the suffix "-1.20".
KAFKA_CONNECTOR_VERSION="3.3.0-${FLINK_VERSION_TAG}"
JDBC_CONNECTOR_VERSION="3.3.0-${FLINK_VERSION_TAG}"
POSTGRES_VERSION="42.7.3"

mkdir -p "$JARS_DIR"

base="https://repo1.maven.org/maven2"

kafka_jar="flink-sql-connector-kafka-${KAFKA_CONNECTOR_VERSION}.jar"
jdbc_jar="flink-connector-jdbc-${JDBC_CONNECTOR_VERSION}.jar"
pg_jar="postgresql-${POSTGRES_VERSION}.jar"

echo "Downloading Flink connector JARs into: $JARS_DIR"

curl -fL "${base}/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR_VERSION}/${kafka_jar}" \
  -o "$JARS_DIR/$kafka_jar"

curl -fL "${base}/org/apache/flink/flink-connector-jdbc/${JDBC_CONNECTOR_VERSION}/${jdbc_jar}" \
  -o "$JARS_DIR/$jdbc_jar"

curl -fL "${base}/org/postgresql/postgresql/${POSTGRES_VERSION}/${pg_jar}" \
  -o "$JARS_DIR/$pg_jar"

echo "Done. Downloaded:"
ls -1 "$JARS_DIR" | sed 's/^/ - /'
