# Etana Energy - June 2026 Allocation

A small command-line Python program that normalises the three meter feeds, reports
data-quality problems, allocates Riverside Hydro generation to the three sites, and
writes a monthly time-of-use summary.

## Layout

```
.
├── main.py            # entry point: wires the three steps together
├── etana/             # the program
│   ├── normalise.py   # load + clean the three feeds
│   ├── allocation.py  # TOU classification and capped allocation
│   └── reports.py     # write the data-quality and summary reports
├── tests/             # pytest suite
├── outputs/           # generated reports (recreated on each run)
├── candidate_pack/    # PROVIDED INPUT (brief PDF + data) - do not edit
├── requirements.txt
└── README.md
```

Everything you write lives at the top level (`main.py`, `etana/`, `tests/`);
`candidate_pack/` is read-only input. Ignore any `__MACOSX/` folder or `.DS_Store`
file - those are macOS zip artefacts, not part of the project.

## Requirements

- Python 3.10+
- `pytest` only if you want to run the tests (the program itself uses the standard library)

```
pip install -r requirements.txt
```

## Run

From the repository root:

```
python main.py
```

Optional paths:

```
python main.py --data-dir candidate_pack/data --out-dir outputs
```

This writes (to `outputs/` by default):

- `data_quality_report.md` - what was found in the data and how it was handled
- `monthly_summary.csv` - one row per site per TOU bucket
- `monthly_summary.md` - readable version including total unallocated generation

## Tests

```
python -m pytest
```

## How it works

1. `etana/normalise.py` loads each provider file and converts everything to a common key:
   the UTC timestamp of the start of each 30-minute interval, with kWh values.
   - MeterFlow: UTC, interval-ending -> subtract 30 minutes to get the interval start.
   - PowerTrack: SAST, interval-beginning, 15-minute average kW -> two readings are
     combined into one half-hour as `0.25 * (kW + kW_next)`.
   - Generation: SAST, kWh. Treated as interval-beginning (see assumptions).
2. `etana/allocation.py` classifies each interval into peak / standard / offpeak using
   the SAST interval start, then allocates `min(percentage * generation, consumption)`.
3. `etana/reports.py` writes the data-quality report and monthly summary.
4. `main.py` wires the three steps together.

## Data quality findings

The program reports these automatically in `data_quality_report.md`:

- MeterFlow uses commas and UTC timestamps; PowerTrack uses semicolons and
  `dd/mm/yyyy` dates; generation uses SAST timestamps. All are converted to one form.
- `MTR-1001` is missing 12 half-hour intervals on 12 June (06:00-11:30 SAST).
- `MTR-1002` has 5 duplicate timestamps. Four are exact repeats; one conflicts
  (`2026-06-08 10:00` SAST, 633.423 vs 1140.161 kWh).
- `MTR-1002` has 48 intervals below 20% of its median on 20 June (12.7-49 kWh),
  which looks like an outage or meter fault.
- `PT-77` is missing two 15-minute readings on 17 June (13:30 and 13:45), so one
  half-hour is incomplete.
- `PT-77` reports 20 identical readings of 352.000 kW on 25 June 08:00-12:45,
  consistent with a frozen meter.
- Generation has 24 consecutive zero-output intervals on 15 June 06:00-17:30.

## Assumptions and decisions

- SAST is treated as a fixed UTC+2 offset, as stated in the config (no DST).
- MeterFlow timestamps are UTC interval-ending, so the interval start is the
  timestamp minus 30 minutes.
- PowerTrack timestamps are SAST interval-beginning with 15-minute average kW.
- The generation file is labelled interval-ending but runs from 2026-06-01 00:00 to
  2026-06-30 23:30. It only tiles June exactly if treated as interval-beginning, so
  that is what the program does. This is recorded in the data-quality report.
- Duplicate timestamps: the last value in the file wins.
- Missing consumption intervals are treated as 0 kWh, so no energy is allocated to
  that site for the gap and its share becomes unallocated.
- An incomplete PowerTrack half-hour is skipped and treated as 0 kWh.
- The TOU bucket is chosen from the SAST interval start time, so the 06:30-07:00
  interval is standard, not peak.
- Wheeling cost is charged on allocated energy at the configured rate.
- Public holidays are treated as normal weekdays, as the config instructs.
- Unallocated generation is the sum, over sites and intervals, of
  `percentage * generation - allocated`. Because the percentages sum to 100, this
  equals total generation minus total allocated energy.

## Written question 1 - redistributing capped energy

After the first pass, compute each site's headroom (`consumption - allocated`) and the
total unallocated energy for the half hour. Distribute the unallocated energy across
sites with headroom, either in proportion to their headroom or in proportion to their
configured percentages, and cap each site again at its headroom. Repeat until either no
unallocated energy remains or no site has headroom. Edge cases are: all sites already
at their cap (energy stays unallocated), a site with missing consumption (treat as zero
headroom), rounding differences that must be reconciled so the sum stays within a
tolerance of the original generation, percentages that do not sum to 100, and the risk
of an infinite loop if redistribution is allowed to oscillate - which is why each pass
must strictly reduce the unallocated amount or stop.

## Written question 2 - corrected data in production

Ingestion should be idempotent and keyed by the natural interval identity
(`meter`, `interval_start`). Each incoming batch is upserted against that key, storing
the raw payload, the provider's version, and a received timestamp, while keeping a
history table of superseded values. A daily job recomputes only the affected intervals
and their downstream aggregates rather than the whole month. If a month has already
been invoiced, corrections should not mutate the issued invoice; instead the system
should record an adjustment or reversal entry for the difference and re-run the
allocation for the corrected intervals. Idempotency keys, ingestion lineage, and a
recalculation queue make re-sent files safe to replay and keep the audit trail intact.
