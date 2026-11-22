import tempfile
from datetime import datetime, timezone
from pathlib import Path

from etana.allocation import allocate, classify_tou
from etana.normalise import SAST, load_meterflow, month_starts_utc


def sast_utc(text):
    return datetime.fromisoformat(text).replace(tzinfo=SAST).astimezone(timezone.utc)


def test_june_has_1440_intervals():
    assert len(month_starts_utc("2026-06")) == 1440


def test_tou_classification():
    assert classify_tou(sast_utc("2026-06-03 07:00:00")) == "peak"
    assert classify_tou(sast_utc("2026-06-03 09:30:00")) == "peak"
    assert classify_tou(sast_utc("2026-06-03 10:00:00")) == "standard"
    assert classify_tou(sast_utc("2026-06-03 06:30:00")) == "standard"
    assert classify_tou(sast_utc("2026-06-03 05:30:00")) == "offpeak"
    assert classify_tou(sast_utc("2026-06-06 08:00:00")) == "offpeak"


def test_allocation_is_capped_and_remainder_unallocated():
    config = {
        "sites": [
            {"site": "A", "meter": "M1", "allocation_pct": 60.0},
            {"site": "B", "meter": "M2", "allocation_pct": 40.0},
        ],
        "wheeling_rates_zar_per_kwh": {"peak": 2.5, "standard": 1.8, "offpeak": 1.1},
    }
    start = month_starts_utc("2026-06")[0]
    generation = {start: 100.0}
    consumption = {("M1", start): 20.0, ("M2", start): 100.0}

    rows, unallocated = allocate(config, generation, consumption, [start])
    by_site = {row["site"]: row for row in rows}

    assert by_site["A"]["allocated_kwh"] == 20.0
    assert by_site["B"]["allocated_kwh"] == 40.0
    assert by_site["B"]["residual_kwh"] == 60.0
    assert abs(unallocated - 40.0) < 1e-9


def test_meterflow_keeps_last_duplicate():
    starts = month_starts_utc("2026-06")
    content = (
        "meter_serial,reading_timestamp_utc,consumption_kwh\n"
        "MTR-1,2026-05-31T22:30:00Z,10\n"
        "MTR-1,2026-05-31T22:30:00Z,12\n"
    )
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "meterflow.csv"
        path.write_text(content, encoding="utf-8")
        readings, issues = load_meterflow(path, starts)

    assert readings[("MTR-1", starts[0])] == 12.0
    assert any("duplicate" in message for _, message in issues)
