import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple


ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)
DOWN_MINUTES_THRESHOLD = 180
ATRISK_MINUTES_THRESHOLD = 60
LOW_FILL_THRESHOLD = 20.0
HIGH_TEMP_THRESHOLD = 36.0


def parse_dt(s: str) -> datetime:
    for fmt in ISO_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unrecognized datetime format: {s!r}")


def date_only(s: str) -> str:
    # Works for both "2024-05-29T00:00:00" and "...246049"
    return s.split("T", 1)[0]


def iter_machine_readings(
    path: str,
    machine_ids: Set[str],
    allowed_dates: Optional[Set[str]] = None,
    max_readings_per_machine: Optional[int] = None,
) -> Dict[str, List[dict]]:
    """
    Extract readings for specific machine IDs from the huge pretty-printed JSON.
    This avoids loading the full file into memory by scanning line-by-line.
    """
    results: Dict[str, List[dict]] = {mid: [] for mid in machine_ids}

    current_mid: Optional[str] = None
    in_target_array = False
    obj_lines: List[str] = []
    obj_depth = 0

    def should_keep_reading(mid: str) -> bool:
        cap = max_readings_per_machine
        return cap is None or len(results[mid]) < cap

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()

            # Detect the start of a machine array:  "123": [
            if not in_target_array and stripped.startswith('"') and stripped.endswith("["):
                try:
                    key_part = stripped.split(":", 1)[0].strip()
                    mid = json.loads(key_part)
                except Exception:
                    continue

                if isinstance(mid, str) and mid in machine_ids and should_keep_reading(mid):
                    current_mid = mid
                    in_target_array = True
                    obj_lines = []
                    obj_depth = 0
                else:
                    current_mid = None
                    in_target_array = False
                continue

            if not in_target_array or current_mid is None:
                continue

            # End of the machine array.
            if stripped.startswith("]"):
                in_target_array = False
                current_mid = None
                continue

            # Collect object text between { ... } and parse each object.
            if "{" in stripped:
                obj_depth += stripped.count("{")
            if obj_depth > 0:
                obj_lines.append(line)
            if "}" in stripped and obj_depth > 0:
                obj_depth -= stripped.count("}")

            if obj_depth == 0 and obj_lines:
                raw_obj = "".join(obj_lines).strip()
                # Objects in an array end with "," in the source; strip trailing comma safely.
                if raw_obj.endswith(","):
                    raw_obj = raw_obj[:-1]
                try:
                    obj = json.loads(raw_obj)
                except json.JSONDecodeError:
                    obj_lines = []
                    continue

                ts = obj.get("timestamp")
                if isinstance(ts, str):
                    if allowed_dates is None or date_only(ts) in allowed_dates:
                        results[current_mid].append(obj)
                obj_lines = []

            if max_readings_per_machine is not None and len(results[current_mid]) >= max_readings_per_machine:
                # Stop scanning this machine; keep scanning file for other machines.
                in_target_array = False
                current_mid = None

    return results


@dataclass
class MachineSummary:
    machine_id: str
    start: datetime
    end: datetime
    readings: int
    on_readings: int
    off_readings: int
    off_minutes: int
    temp_on_avg: Optional[float]
    temp_on_min: Optional[float]
    temp_on_max: Optional[float]
    pct_avg: Optional[float]
    pct_min: Optional[float]
    pct_max: Optional[float]
    current_fill_pct: Optional[float]
    cups_total: int
    cups_per_hour: Optional[float]
    cups_value_min: Optional[int]
    cups_value_max: Optional[int]
    maintenance_clean_events: int
    maintenance_filter_events: int
    top_hours: List[Tuple[str, int]]
    status: str


def summarize_machine(machine_id: str, rows: List[dict]) -> Optional[MachineSummary]:
    if not rows:
        return None

    rows_sorted = sorted(rows, key=lambda r: r.get("timestamp", ""))
    times = [parse_dt(r["timestamp"]) for r in rows_sorted if isinstance(r.get("timestamp"), str)]
    if not times:
        return None
    start, end = times[0], times[-1]

    temps_on: List[float] = []
    pct: List[float] = []
    cups_total = 0
    cups_vals: List[int] = []
    on = 0
    off = 0

    # Data seems to be in 5-minute increments; estimate downtime as 5 minutes per off reading.
    prev_counter: Optional[int] = None
    hourly: Dict[str, int] = {}
    for r in rows_sorted:
        if isinstance(r.get("percentage_full"), (int, float)):
            pct.append(float(r["percentage_full"]))
        if r.get("is_on") is True:
            on += 1
            if isinstance(r.get("temperature"), (int, float)):
                temps_on.append(float(r["temperature"]))
        elif r.get("is_on") is False:
            off += 1
        if isinstance(r.get("slushies_filled"), int):
            counter = int(r["slushies_filled"])
            cups_vals.append(counter)
            # Interpret as a counter that can reset; count only positive deltas.
            if prev_counter is not None:
                delta = max(0, counter - prev_counter)
                cups_total += delta
                ts_s = r.get("timestamp")
                if isinstance(ts_s, str):
                    ts = parse_dt(ts_s)
                    hour_key = ts.strftime("%Y-%m-%d %H:00")
                    hourly[hour_key] = hourly.get(hour_key, 0) + delta
            prev_counter = counter

    off_minutes = off * 5
    hours = max((end - start).total_seconds() / 3600.0, 0.0001)

    # Count maintenance date changes as "events" in this sample window.
    last_cleaned_values = [r.get("last_cleaned") for r in rows_sorted if isinstance(r.get("last_cleaned"), str)]
    last_filter_values = [
        r.get("last_time_filter_replaced")
        for r in rows_sorted
        if isinstance(r.get("last_time_filter_replaced"), str)
    ]
    clean_events = sum(1 for i in range(1, len(last_cleaned_values)) if last_cleaned_values[i] != last_cleaned_values[i - 1])
    filter_events = sum(1 for i in range(1, len(last_filter_values)) if last_filter_values[i] != last_filter_values[i - 1])

    def safe_avg(xs: List[float]) -> Optional[float]:
        return (sum(xs) / len(xs)) if xs else None

    current_fill_pct = None
    if isinstance(rows_sorted[-1].get("percentage_full"), (int, float)):
        current_fill_pct = float(rows_sorted[-1]["percentage_full"])

    temp_avg = safe_avg(temps_on)
    if off_minutes >= DOWN_MINUTES_THRESHOLD:
        status = "Down"
    elif (
        off_minutes >= ATRISK_MINUTES_THRESHOLD
        or
        (current_fill_pct is not None and current_fill_pct < LOW_FILL_THRESHOLD)
        or (temp_avg is not None and temp_avg > HIGH_TEMP_THRESHOLD)
    ):
        status = "AtRisk"
    else:
        status = "Healthy"

    return MachineSummary(
        machine_id=machine_id,
        start=start,
        end=end,
        readings=len(rows_sorted),
        on_readings=on,
        off_readings=off,
        off_minutes=off_minutes,
        temp_on_avg=safe_avg(temps_on),
        temp_on_min=min(temps_on) if temps_on else None,
        temp_on_max=max(temps_on) if temps_on else None,
        pct_avg=safe_avg(pct),
        pct_min=min(pct) if pct else None,
        pct_max=max(pct) if pct else None,
        current_fill_pct=current_fill_pct,
        cups_total=cups_total,
        cups_per_hour=cups_total / hours if hours else None,
        cups_value_min=min(cups_vals) if cups_vals else None,
        cups_value_max=max(cups_vals) if cups_vals else None,
        maintenance_clean_events=clean_events,
        maintenance_filter_events=filter_events,
        top_hours=sorted(hourly.items(), key=lambda kv: kv[1], reverse=True)[:3],
        status=status,
    )


def main() -> None:
    data_path = "slushi docs/slushie_machines_data_huge.json"

    # Simple, readable sample: a few machines and one day.
    machine_ids = {"1", "2", "3"}
    allowed_dates = {"2024-05-29"}

    extracted = iter_machine_readings(
        path=data_path,
        machine_ids=machine_ids,
        allowed_dates=allowed_dates,
        max_readings_per_machine=24 * 12,  # up to 24h at 5-min intervals
    )

    summaries: List[MachineSummary] = []
    for mid in sorted(machine_ids, key=int):
        s = summarize_machine(mid, extracted.get(mid, []))
        if s:
            summaries.append(s)

    summary_export = []
    for s in summaries:
        summary_export.append(
            {
                "machine_id": s.machine_id,
                "status": s.status,
                "off_minutes": s.off_minutes,
                "percentage_full": round(s.current_fill_pct, 2) if s.current_fill_pct is not None else None,
                "temp_avg": round(s.temp_on_avg, 2) if s.temp_on_avg is not None else None,
                "cups_total_est": s.cups_total,
            }
        )

    with open("sample_machine_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_export, f, indent=2)

    # Print a small table (markdown-friendly) - Person 2 output fields only.
    print("| machine_id | status | off_minutes | percentage_full | temp_avg | cups_total_est |")
    print("|---:|:---|---:|---:|---:|---:|")
    for s in summaries:
        print(
            "| "
            + " | ".join(
                [
                    s.machine_id,
                    s.status,
                    str(s.off_minutes),
                    f"{s.current_fill_pct:.2f}" if s.current_fill_pct is not None else "NA",
                    f"{s.temp_on_avg:.2f}" if s.temp_on_avg is not None else "NA",
                    str(s.cups_total),
                ]
            )
            + " |"
        )


if __name__ == "__main__":
    main()

