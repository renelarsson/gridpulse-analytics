import argparse
import os

import requests


DEFAULT_REPORT_DATE = "20260317"
DEFAULT_OUTPUT_DIR = "data/raw"
URL_TEMPLATE = "https://www.iso-ne.com/histRpts/da-lmp/WW_DALMP_ISO_{report_date}.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download one ISO-NE day-ahead hourly CSV report into the raw data folder."
    )
    parser.add_argument(
        "--report-date",
        default=DEFAULT_REPORT_DATE,
        help="Report date in YYYYMMDD form, for example 20260317.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Optional direct report URL. If omitted, the URL is built from --report-date.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional output path. If omitted, the raw filename is derived from the report date.",
    )
    return parser.parse_args()


def build_report_url(report_date: str) -> str:
    return URL_TEMPLATE.format(report_date=report_date)


def build_output_path(report_date: str) -> str:
    filename = f"WW_DALMP_ISO_{report_date}.csv"
    return os.path.join(DEFAULT_OUTPUT_DIR, filename)


def download_day_ahead_file(url: str, output_path: str) -> None:
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    # Keep the raw folder reproducible even when downloading a new report date.
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Stream the file in chunks so the script does not need the whole report in memory.
    with open(output_path, "wb") as file_handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_handle.write(chunk)


def main() -> None:
    args = parse_args()
    url = args.url or build_report_url(args.report_date)
    output_path = args.output_path or build_output_path(args.report_date)

    download_day_ahead_file(url, output_path)
    print(f"Downloaded {url}")
    print(f"Saved raw file to {output_path}")


if __name__ == "__main__":
    main()