import json
import os
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote_plus

import boto3  # type: ignore[import-not-found]


ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)
DOWN_MINUTES_THRESHOLD = 180
ATRISK_MINUTES_THRESHOLD = 60
LOW_FILL_THRESHOLD = 20.0
HIGH_TEMP_THRESHOLD = 36.0
READING_INTERVAL_MINUTES = 5
DEFAULT_MACHINE_IDS = ("1", "2", "3")
DEFAULT_ALLOWED_DATES = ("2024-05-29",)

s3_client = boto3.client("s3")
dynamodb_resource = boto3.resource("dynamodb")


def parse_dt(value: str) -> datetime:
    for fmt in ISO_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized datetime format: {value!r}")


def date_only(value: str) -> str:
    return value.split("T", 1)[0]


def safe_average(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def parse_machine_ids(value: Any) -> List[str]:
    if value is None:
        return list(DEFAULT_MACHINE_IDS)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return list(DEFAULT_MACHINE_IDS)


def parse_allowed_dates(value: Any) -> Optional[List[str]]:
    if value is None:
        return list(DEFAULT_ALLOWED_DATES)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return list(DEFAULT_ALLOWED_DATES)


def extract_bucket_and_key(event: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    if event.get("bucket") and event.get("key"):
        return event["bucket"], event["key"]

    records = event.get("Records")
    if isinstance(records, list) and records:
        s3_info = records[0].get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name")
        key = s3_info.get("object", {}).get("key")
        return bucket, unquote_plus(key) if isinstance(key, str) else key

    return None, None


def load_source_payload(event: Dict[str, Any]) -> Dict[str, List[dict]]:
    if isinstance(event.get("body"), str):
        body = json.loads(event["body"])
        if isinstance(body, dict):
            event = {**body, **{k: v for k, v in event.items() if k != "body"}}

    if isinstance(event.get("payload"), dict):
        return event["payload"]

    if isinstance(event.get("payload_json"), str):
        return json.loads(event["payload_json"])

    bucket, key = extract_bucket_and_key(event)
    if not bucket or not key:
        raise ValueError("Provide `bucket` and `key`, an S3 trigger event, or inline `payload` data.")

    response = s3_client.get_object(Bucket=bucket, Key=key)
    raw_data = response["Body"].read().decode("utf-8")
    return json.loads(raw_data)


def filter_machine_rows(
    payload: Dict[str, List[dict]],
    machine_ids: Sequence[str],
    allowed_dates: Optional[Sequence[str]],
) -> Dict[str, List[dict]]:
    allowed_date_set = set(allowed_dates) if allowed_dates else None
    filtered: Dict[str, List[dict]] = {}

    for machine_id in machine_ids:
        rows = payload.get(machine_id, [])
        machine_rows: List[dict] = []
        for row in rows:
            timestamp = row.get("timestamp")
            if not isinstance(timestamp, str):
                continue
            if allowed_date_set and date_only(timestamp) not in allowed_date_set:
                continue
            machine_rows.append(row)
        filtered[machine_id] = machine_rows

    return filtered


def summarize_machine(machine_id: str, rows: List[dict]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None

    rows_sorted = sorted(rows, key=lambda row: row.get("timestamp", ""))
    valid_times = [parse_dt(row["timestamp"]) for row in rows_sorted if isinstance(row.get("timestamp"), str)]
    if not valid_times:
        return None

    start = valid_times[0]
    end = valid_times[-1]
    on_temperatures: List[float] = []
    fill_levels: List[float] = []
    off_readings = 0
    cups_total = 0
    previous_counter: Optional[int] = None
    hourly_cups: Dict[str, int] = {}

    for row in rows_sorted:
        percentage_full = row.get("percentage_full")
        if isinstance(percentage_full, (int, float)):
            fill_levels.append(float(percentage_full))

        is_on = row.get("is_on")
        if is_on is True:
            temperature = row.get("temperature")
            if isinstance(temperature, (int, float)):
                on_temperatures.append(float(temperature))
        elif is_on is False:
            off_readings += 1

        slushies_filled = row.get("slushies_filled")
        if isinstance(slushies_filled, int):
            if previous_counter is not None:
                delta = max(0, slushies_filled - previous_counter)
                cups_total += delta
                if delta:
                    timestamp = parse_dt(row["timestamp"])
                    hour_key = timestamp.strftime("%Y-%m-%d %H:00")
                    hourly_cups[hour_key] = hourly_cups.get(hour_key, 0) + delta
            previous_counter = slushies_filled

    off_minutes = off_readings * READING_INTERVAL_MINUTES
    current_fill_pct = None
    if isinstance(rows_sorted[-1].get("percentage_full"), (int, float)):
        current_fill_pct = float(rows_sorted[-1]["percentage_full"])
    temp_avg = safe_average(on_temperatures)

    if off_minutes >= DOWN_MINUTES_THRESHOLD:
        status = "Down"
    elif (
        off_minutes >= ATRISK_MINUTES_THRESHOLD
        or (current_fill_pct is not None and current_fill_pct < LOW_FILL_THRESHOLD)
        or (temp_avg is not None and temp_avg > HIGH_TEMP_THRESHOLD)
    ):
        status = "AtRisk"
    else:
        status = "Healthy"

    top_hours = [
        {"hour": hour, "cups_est": cups}
        for hour, cups in sorted(hourly_cups.items(), key=lambda item: item[1], reverse=True)[:3]
    ]

    return {
        "machine_id": machine_id,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "status": status,
        "off_minutes": off_minutes,
        "percentage_full": round(current_fill_pct, 2) if current_fill_pct is not None else None,
        "temp_avg": round(temp_avg, 2) if temp_avg is not None else None,
        "cups_total_est": cups_total,
        "top_hours": top_hours,
    }


def to_dynamodb_item(summary: Dict[str, Any]) -> Dict[str, Any]:
    item: Dict[str, Any] = {}
    for key, value in summary.items():
        if isinstance(value, float):
            item[key] = Decimal(str(value))
        elif isinstance(value, list):
            converted_list = []
            for entry in value:
                converted_entry = {}
                for entry_key, entry_value in entry.items():
                    if isinstance(entry_value, float):
                        converted_entry[entry_key] = Decimal(str(entry_value))
                    else:
                        converted_entry[entry_key] = entry_value
                converted_list.append(converted_entry)
            item[key] = converted_list
        else:
            item[key] = value
    return item


def write_summaries_to_dynamodb(table_name: str, summaries: Sequence[Dict[str, Any]]) -> None:
    table = dynamodb_resource.Table(table_name)
    with table.batch_writer() as batch:
        for summary in summaries:
            batch.put_item(Item=to_dynamodb_item(summary))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    machine_ids = parse_machine_ids(event.get("machine_ids") or os.getenv("MACHINE_IDS"))
    allowed_dates = parse_allowed_dates(event.get("allowed_dates") or os.getenv("ALLOWED_DATES"))
    table_name = event.get("table_name") or os.getenv("DYNAMODB_TABLE")

    payload = load_source_payload(event)
    filtered_rows = filter_machine_rows(payload, machine_ids, allowed_dates)

    summaries = []
    for machine_id in machine_ids:
        summary = summarize_machine(machine_id, filtered_rows.get(machine_id, []))
        if summary:
            summaries.append(summary)

    if table_name:
        write_summaries_to_dynamodb(table_name, summaries)

    response_body = {
        "machine_count": len(summaries),
        "summaries": summaries,
        "table_name": table_name,
    }

    return {
        "statusCode": 200,
        "body": json.dumps(response_body),
    }
