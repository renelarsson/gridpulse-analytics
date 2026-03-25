import argparse
import csv
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import dlt


DEFAULT_INPUT_PATH = "data/raw/WW_DALMP_ISO_20260317.csv"
DEFAULT_PIPELINE_NAME = "iso_ne_day_ahead_raw"
DEFAULT_DATASET_NAME = "iso_ne_raw"
DEFAULT_TABLE_NAME = "day_ahead_hourly_lmp_raw"
DEFAULT_DESTINATION = "postgres"
DEFAULT_POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/market_data"

# These are the vendor column names from the ISO-NE header row that starts with `H`.
EXPECTED_SOURCE_COLUMNS = [
	"Date",
	"Hour Ending",
	"Location ID",
	"Location Name",
	"Location Type",
	"Locational Marginal Price",
	"Energy Component",
	"Congestion Component",
	"Marginal Loss Component",
]

# The raw landing table keeps vendor values but uses SQL-friendly column names.
RAW_TO_SQL_COLUMNS = {
	"Date": "market_date",
	"Hour Ending": "hour_ending",
	"Location ID": "location_id",
	"Location Name": "location_name",
	"Location Type": "location_type",
	"Locational Marginal Price": "locational_marginal_price",
	"Energy Component": "energy_component",
	"Congestion Component": "congestion_component",
	"Marginal Loss Component": "marginal_loss_component",
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Load ISO-NE day-ahead raw CSV rows into a dlt destination."
	)
	parser.add_argument(
		"--input-path",
		dest="input_paths",
		action="append",
		default=[],
		help="Path to a raw ISO-NE CSV file. Repeat the flag to backfill multiple files.",
	)
	parser.add_argument(
		"--pipeline-name",
		default=DEFAULT_PIPELINE_NAME,
		help="dlt pipeline name.",
	)
	parser.add_argument(
		"--dataset-name",
		default=DEFAULT_DATASET_NAME,
		help="Destination dataset or schema name.",
	)
	parser.add_argument(
		"--table-name",
		default=DEFAULT_TABLE_NAME,
		help="Destination table name.",
	)
	parser.add_argument(
		"--destination",
		default=DEFAULT_DESTINATION,
		help="dlt destination name, for example postgres or bigquery.",
	)
	parser.add_argument(
		"--destination-credentials",
		"--destination-dsn",
		dest="destination_credentials",
		default=None,
		help=(
			"Destination credentials. For postgres this is a DSN. "
			"For bigquery this can be a service-account JSON path or other dlt-supported credential input."
		),
	)
	parser.add_argument(
		"--write-disposition",
		choices=["append", "replace"],
		default="replace",
		help="Whether to replace or append rows in the destination table.",
	)
	args = parser.parse_args()
	if not args.input_paths:
		args.input_paths = [DEFAULT_INPUT_PATH]
	if args.destination_credentials is None and args.destination == "postgres":
		args.destination_credentials = os.environ.get("DLT_POSTGRES_DSN", DEFAULT_POSTGRES_DSN)
	if args.destination_credentials is None and args.destination == "bigquery":
		args.destination_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
	# Append with one file is allowed, but the usual backfill case passes multiple --input-path flags.
	if args.write_disposition == "append" and len(args.input_paths) == 1:
		print(
			"Warning: append mode was requested with one input file. "
			"This is valid, but multi-file backfill usually repeats --input-path.",
			file=sys.stderr,
		)
	# Keep the default local postgres pipeline state separate from alternate destinations.
	if args.pipeline_name == DEFAULT_PIPELINE_NAME and args.destination != DEFAULT_DESTINATION:
		args.pipeline_name = f"{DEFAULT_PIPELINE_NAME}_{args.destination}"
	return args


def iter_day_ahead_raw_rows(input_path: str) -> Iterator[dict[str, str]]:
	with open(input_path, newline="", encoding="utf-8") as csv_file:
		reader = csv.reader(csv_file)

		try:
			# ISO-NE reports begin with 4 metadata rows, then a field-name row and a field-type row.
			for _ in range(4):
				next(reader)
			header_row = next(reader)
			next(reader)
		except StopIteration as exc:
			raise ValueError(f"Input file is too short to be a valid ISO-NE report: {input_path}") from exc

		if not header_row or header_row[0] != "H":
			raise ValueError(f"Expected a header row starting with 'H' in {input_path}")

		source_columns = header_row[1:]
		if source_columns != EXPECTED_SOURCE_COLUMNS:
			raise ValueError(
				"Unexpected raw header columns. "
				f"Expected {EXPECTED_SOURCE_COLUMNS}, got {source_columns}"
			)

		for row_number, row in enumerate(reader, start=7):
			# `D` marks a data row in this report family; other record types are not market rows.
			if not row or row[0] != "D":
				continue

			source_values = row[1:]
			if len(source_values) != len(source_columns):
				raise ValueError(
					f"Row {row_number} in {input_path} has {len(source_values)} values; "
					f"expected {len(source_columns)}"
				)

			# Preserve the raw values as strings for the first dlt landing step.
			payload = {
				RAW_TO_SQL_COLUMNS[column_name]: value
				for column_name, value in zip(source_columns, source_values, strict=True)
			}
			# Keep enough traceability to get back to the exact source file and row.
			payload["source_file"] = os.path.basename(input_path)
			payload["source_row_number"] = str(row_number)
			yield payload


def iter_multiple_day_ahead_raw_rows(input_paths: list[str]) -> Iterator[dict[str, str]]:
	# Preserve CLI order so a backfill run is easy to reason about from the terminal log.
	for input_path in input_paths:
		yield from iter_day_ahead_raw_rows(input_path)


def build_validation_query(destination: str, dataset_name: str, table_name: str) -> str:
	if destination == "postgres":
		return f'SELECT COUNT(*) AS row_count FROM "{dataset_name}"."{table_name}";'
	if destination == "bigquery":
		return f"SELECT COUNT(*) AS row_count FROM `{dataset_name}.{table_name}`;"
	return f"SELECT COUNT(*) AS row_count FROM {dataset_name}.{table_name};"


def resolve_destination_credentials(destination: str, credentials: str | None) -> object | None:
	if credentials is None:
		return None
	if destination != "bigquery":
		return credentials

	credential_path = Path(credentials)
	if credential_path.exists():
		# dlt accepts the parsed service-account document for BigQuery more reliably than a raw path string.
		return json.loads(credential_path.read_text(encoding="utf-8"))
	return credentials


def main() -> None:
	args = parse_args()

	# A dlt resource is the iterable dataset that the pipeline will load.
	resource = dlt.resource(
		iter_multiple_day_ahead_raw_rows(args.input_paths),
		name=args.table_name,
		table_name=args.table_name,
		write_disposition=args.write_disposition,
	)

	# The pipeline binds the resource to the chosen destination and dataset/schema.
	pipeline = dlt.pipeline(
		pipeline_name=args.pipeline_name,
		destination=args.destination,
		dataset_name=args.dataset_name,
		progress="log",
	)

	# `run` performs extract, normalize, and load for this one local raw-ingestion step.
	load_kwargs: dict[str, object] = {}
	resolved_credentials = resolve_destination_credentials(args.destination, args.destination_credentials)
	if resolved_credentials is not None:
		load_kwargs["credentials"] = resolved_credentials
	load_info = pipeline.run(resource, **load_kwargs)

	print(load_info)
	# Print the file list so repeated local runs and backfills are visible in command output.
	print(f"Loaded raw CSV rows from {len(args.input_paths)} file(s):")
	for input_path in args.input_paths:
		print(f"- {input_path}")
	print(f"Destination dataset: {args.dataset_name}")
	print(f"Destination table: {args.table_name}")
	print("Validation query:")
	print(build_validation_query(args.destination, args.dataset_name, args.table_name))


if __name__ == "__main__":
	main()