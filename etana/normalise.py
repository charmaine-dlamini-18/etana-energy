import csv
import statistics
from calendar import monthrange
from datetime import datetime, timedelta, timezone

# Time zone and interval sizes used throughout the module.
SAST = timezone(timedelta(hours=2))
INTERVAL = timedelta(minutes=30)
QUARTER = timedelta(minutes=15)


def month_starts_sast(billing_month):
    # Build every 30-minute start time for the month in local time.
    year, month = (int(part) for part in billing_month.split("-"))
    days = monthrange(year, month)[1]
    first = datetime(year, month, 1, tzinfo=SAST)
    return [first + INTERVAL * index for index in range(days * 48)]


def month_starts_utc(billing_month):
    # Same interval starts, converted to UTC.
    return [start.astimezone(timezone.utc) for start in month_starts_sast(billing_month)]


def parse_utc(text):
    # Parse an ISO timestamp, treating a trailing Z as UTC.
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def load_meterflow(path, expected_starts):
    # Readings keyed by (meter, interval start).
    readings = {}
    duplicates = {}
    conflicts = []

    # Read each CSV row and convert interval-ending times to interval starts.
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            meter = row["meter_serial"].strip()
            end = parse_utc(row["reading_timestamp_utc"].strip())
            start = end - INTERVAL
            kwh = float(row["consumption_kwh"])
            key = (meter, start)
            # Track duplicate timestamps; the last value wins.
            if key in readings:
                duplicates[meter] = duplicates.get(meter, 0) + 1
                if readings[key] != kwh:
                    conflicts.append((meter, start, readings[key], kwh))
            readings[key] = kwh

    # Turn duplicates and conflicts into data quality notes.
    issues = []
    for meter, count in sorted(duplicates.items()):
        issues.append(("MeterFlow", f"{meter}: {count} duplicate interval(s); kept the last value"))
    for meter, start, old, new in conflicts:
        issues.append((
            "MeterFlow",
            f"{meter}: conflicting duplicate at {start.astimezone(SAST):%Y-%m-%d %H:%M} SAST; "
            f"kept {new:.3f} kWh instead of {old:.3f} kWh",
        ))

    # Check each meter for missing intervals and suspiciously low readings.
    for meter in sorted({meter for meter, _ in readings}):
        present = {start for (m, start) in readings if m == meter}
        missing = [start for start in expected_starts if start not in present]
        issues.append(("MeterFlow", f"{meter}: {len(present)} intervals present, {len(missing)} missing"))
        if missing:
            issues.append((
                "MeterFlow",
                f"{meter}: gap from {missing[0].astimezone(SAST):%Y-%m-%d %H:%M} to "
                f"{missing[-1].astimezone(SAST):%H:%M} SAST",
            ))
        values = [value for (m, _), value in readings.items() if m == meter]
        median = statistics.median(values)
        low = sorted(value for value in values if value < 0.2 * median)
        if low:
            issues.append((
                "MeterFlow",
                f"{meter}: {len(low)} interval(s) below 20% of the meter median "
                f"({median:.1f} kWh); lowest {low[0]:.3f} kWh",
            ))

    return readings, issues


def load_powertrack(path, sast_starts):
    # Raw 15-minute kW readings keyed by (meter, start).
    quarter = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            meter = row["serial"].strip()
            day, month, year = (int(part) for part in row["reading_date"].split("/"))
            hour, minute = (int(part) for part in row["reading_time"].split(":"))
            start = datetime(year, month, day, hour, minute, tzinfo=SAST)
            quarter[(meter, start)] = float(row["kw"])

    readings = {}
    issues = []
    # Combine each pair of 15-minute readings into a 30-minute kWh value.
    for meter in sorted({meter for meter, _ in quarter}):
        missing = []
        for start in sast_starts:
            first = quarter.get((meter, start))
            second = quarter.get((meter, start + QUARTER))
            # Skip half-hours where either quarter is missing.
            if first is None or second is None:
                missing.append(start)
                continue
            readings[(meter, start.astimezone(timezone.utc))] = 0.25 * (first + second)

        present = {start for (m, start) in readings if m == meter}
        issues.append(("PowerTrack", f"{meter}: {len(present)} half-hours present, {len(missing)} incomplete"))
        if missing:
            issues.append((
                "PowerTrack",
                f"{meter}: incomplete half-hour starting {missing[0]:%Y-%m-%d %H:%M} SAST",
            ))
        # Report stretches of identical readings that may mean a stuck meter.
        for run in frozen_runs(meter, quarter):
            value = quarter[(meter, run[0])]
            issues.append((
                "PowerTrack",
                f"{meter}: {len(run)} consecutive readings at {value:.3f} kW from "
                f"{run[0]:%Y-%m-%d %H:%M} to {run[-1]:%H:%M} SAST; possible frozen meter",
            ))

    return readings, issues


def frozen_runs(meter, quarter):
    # Find runs of 4+ consecutive quarters with the same value.
    times = sorted(start for (m, start) in quarter if m == meter)
    runs = []
    current = []
    for start in times:
        same_value = current and quarter[(meter, start)] == quarter[(meter, current[-1])]
        if same_value and start - current[-1] == QUARTER:
            current.append(start)
        else:
            if len(current) >= 4:
                runs.append(current)
            current = [start]
    if len(current) >= 4:
        runs.append(current)
    return runs


def load_generation(path, expected_starts):
    # Generation keyed by UTC interval start.
    generation = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            stamp = datetime.fromisoformat(row["timestamp_sast"].strip()).replace(tzinfo=SAST)
            generation[stamp.astimezone(timezone.utc)] = float(row["generation_kwh"])

    # Report missing intervals and periods of zero output.
    issues = []
    present = set(generation)
    missing = [start for start in expected_starts if start not in present]
    issues.append(("Generation", f"{len(present)} intervals present, {len(missing)} missing"))
    if missing:
        issues.append((
            "Generation",
            f"missing intervals from {missing[0].astimezone(SAST):%Y-%m-%d %H:%M} to "
            f"{missing[-1].astimezone(SAST):%H:%M} SAST",
        ))

    zeros = sorted(start for start, value in generation.items() if value == 0.0)
    if zeros:
        issues.append((
            "Generation",
            f"{len(zeros)} interval(s) at zero output from "
            f"{zeros[0].astimezone(SAST):%Y-%m-%d %H:%M} to {zeros[-1].astimezone(SAST):%H:%M} SAST",
        ))

    # Record the timestamp range and the interval-labelling decision.
    first = min(generation).astimezone(SAST)
    last = max(generation).astimezone(SAST)
    issues.append((
        "Generation",
        f"timestamps run {first:%Y-%m-%d %H:%M} to {last:%Y-%m-%d %H:%M} SAST; labelled "
        "interval-ending in the brief but treated as interval-beginning so the file tiles June exactly",
    ))
    return generation, issues
