import argparse
import csv
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

from kafka import KafkaProducer


DEFAULT_BROKER_URL = "localhost:19092"
DEFAULT_TOPIC_NAME = "day_ahead_events"
DEFAULT_NORMALIZED_DATA_PATH = Path("data/normalized/WW_DALMP_ISO_20260317_normalized.csv")
EVENT_ORDERING_FIELD = "market_timestamp_utc"
DEFAULT_REPLAY_DELAY_SECONDS = 0.031
DEFAULT_WATERMARK_SENTINEL_OFFSET_SECONDS = 3605
WATERMARK_SENTINEL_FIELD = "replay_control"
WATERMARK_SENTINEL_VALUE = "watermark_flush"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for replay configuration."""
    parser = argparse.ArgumentParser(
        description="Replay normalized ISO-NE day-ahead events into Redpanda."
    )
    parser.add_argument(
        "--input-path",
        type=Path,
        default=DEFAULT_NORMALIZED_DATA_PATH,
        help="Path to the normalized CSV file to replay.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_REPLAY_DELAY_SECONDS,
        help="Delay between published events in seconds.",
    )
    parser.add_argument(
        "--broker-url",
        default=DEFAULT_BROKER_URL,
        help="Kafka-compatible broker address.",
    )
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC_NAME,
        help="Topic that receives replayed events.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-event publish logs; print only summaries.",
    )
    parser.add_argument(
        "--verify-acks",
        action="store_true",
        help=(
            "Wait for broker acknowledgements for each produced message and "
            "verify the acknowledged count matches the records published in this run."
        ),
    )
    parser.add_argument(
        "--acks-timeout-seconds",
        type=float,
        default=10.0,
        help="Timeout (seconds) when waiting for broker acknowledgements.",
    )
    parser.add_argument(
        "--emit-watermark-sentinel",
        action="store_true",
        help=(
            "Publish one control record after the final real event so a finite replay "
            "can advance the Flink watermark and close the last hourly windows."
        ),
    )
    parser.add_argument(
        "--watermark-sentinel-offset-seconds",
        type=int,
        default=DEFAULT_WATERMARK_SENTINEL_OFFSET_SECONDS,
        help=(
            "How far beyond the final real event timestamp to place the watermark "
            "sentinel. The default is one hour plus five seconds."
        ),
    )
    return parser.parse_args()


def load_normalized_data(file_path: Path) -> list[dict[str, str]]:
    """Load normalized events from the CSV created by normalize_day_ahead.py."""
    with file_path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        events = list(reader)

    events.sort(
        key=lambda event: (
            event[EVENT_ORDERING_FIELD],
            event["location_id"],
            event["location_name"],
        )
    )
    return events


def build_watermark_sentinel_event(
    events: list[dict[str, str]],
    offset_seconds: int,
) -> dict[str, str]:
    """Create one control event beyond the final real timestamp to flush windows."""
    if not events:
        raise ValueError("Cannot build a watermark sentinel without at least one event.")

    last_event = events[-1]
    last_timestamp = datetime.fromisoformat(last_event[EVENT_ORDERING_FIELD])
    sentinel_timestamp = last_timestamp + timedelta(seconds=offset_seconds)

    sentinel_event = {key: "" for key in last_event}
    sentinel_event[EVENT_ORDERING_FIELD] = sentinel_timestamp.strftime("%Y-%m-%d %H:%M:%S+00:00")
    sentinel_event[WATERMARK_SENTINEL_FIELD] = WATERMARK_SENTINEL_VALUE
    return sentinel_event


def replay_events(
    producer: KafkaProducer,
    topic: str,
    events: list[dict[str, str]],
    delay_seconds: float = DEFAULT_REPLAY_DELAY_SECONDS,
    quiet: bool = False,
    verify_acks: bool = False,
    acks_timeout_seconds: float = 10.0,
    emit_watermark_sentinel: bool = False,
    watermark_sentinel_offset_seconds: int = DEFAULT_WATERMARK_SENTINEL_OFFSET_SECONDS,
) -> tuple[int, int]:
    """Publish normalized events one-by-one in a deterministic order."""
    sent_count = 0
    acked_count = 0
    events_to_publish = list(events)
    if emit_watermark_sentinel:
        events_to_publish.append(
            build_watermark_sentinel_event(
                events,
                offset_seconds=watermark_sentinel_offset_seconds,
            )
        )

    for event in events_to_publish:
        future = producer.send(topic, value=event)
        if verify_acks:
            future.get(timeout=acks_timeout_seconds)
            acked_count += 1
        if not quiet:
            print(
                "published",
                event[EVENT_ORDERING_FIELD],
                event["location_id"],
                event["location_name"],
            )
        sent_count += 1
        time.sleep(delay_seconds)

    producer.flush()
    return sent_count, acked_count


def main() -> None:
    """Main entry point for the replay script."""
    args = parse_args()

    if args.delay_seconds < 0:
        raise ValueError("--delay-seconds must be zero or greater.")

    if args.acks_timeout_seconds <= 0:
        raise ValueError("--acks-timeout-seconds must be greater than zero.")

    if args.watermark_sentinel_offset_seconds <= 0:
        raise ValueError("--watermark-sentinel-offset-seconds must be greater than zero.")

    if not args.input_path.exists():
        raise FileNotFoundError(
            "Normalized CSV not found at "
            f"{args.input_path}. Run src.ingestion.normalize_day_ahead first."
        )

    producer = KafkaProducer(
        bootstrap_servers=args.broker_url,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        acks="all" if args.verify_acks else 1,
    )

    events = load_normalized_data(args.input_path)
    input_row_count = len(events)
    print(
        f"starting replay: file={args.input_path} topic={args.topic} "
        f"events={input_row_count} delay_seconds={args.delay_seconds} "
        f"verify_acks={args.verify_acks} "
        f"emit_watermark_sentinel={args.emit_watermark_sentinel}"
    )

    start_time = perf_counter()
    try:
        sent_count, acked_count = replay_events(
            producer,
            args.topic,
            events,
            delay_seconds=args.delay_seconds,
            quiet=args.quiet,
            verify_acks=args.verify_acks,
            acks_timeout_seconds=args.acks_timeout_seconds,
            emit_watermark_sentinel=args.emit_watermark_sentinel,
            watermark_sentinel_offset_seconds=args.watermark_sentinel_offset_seconds,
        )
    finally:
        producer.close()
    elapsed_seconds = perf_counter() - start_time

    expected_acked_count = input_row_count + int(args.emit_watermark_sentinel)
    if args.verify_acks and acked_count != expected_acked_count:
        raise RuntimeError(
            "Replay verification failed: "
            f"expected_acked={expected_acked_count} acked={acked_count}"
        )

    print(
        f"Replay completed: input_rows={input_row_count} sent={sent_count} "
        f"acked={acked_count if args.verify_acks else 'n/a'} "
        f"elapsed_seconds={elapsed_seconds:.3f} topic={args.topic} file={args.input_path}"
    )


if __name__ == "__main__":
    main()