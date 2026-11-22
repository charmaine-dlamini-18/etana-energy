# Data Quality Report

Findings recorded while normalising the three input files.

## MeterFlow

- MTR-1002: 5 duplicate interval(s); kept the last value
- MTR-1002: conflicting duplicate at 2026-06-08 10:00 SAST; kept 1140.161 kWh instead of 633.423 kWh
- MTR-1001: 1428 intervals present, 12 missing
- MTR-1001: gap from 2026-06-12 06:00 to 11:30 SAST
- MTR-1002: 1440 intervals present, 0 missing
- MTR-1002: 48 interval(s) below 20% of the meter median (300.8 kWh); lowest 12.722 kWh

## PowerTrack

- PT-77: 1439 half-hours present, 1 incomplete
- PT-77: incomplete half-hour starting 2026-06-17 13:30 SAST
- PT-77: 20 consecutive readings at 352.000 kW from 2026-06-25 08:00 to 12:45 SAST; possible frozen meter

## Generation

- 1440 intervals present, 0 missing
- 24 interval(s) at zero output from 2026-06-15 06:00 to 17:30 SAST
- timestamps run 2026-06-01 00:00 to 2026-06-30 23:30 SAST; labelled interval-ending in the brief but treated as interval-beginning so the file tiles June exactly

## Decisions

- Duplicate timestamps: the last value in the file is kept.
- Missing consumption intervals: treated as 0 kWh, so no energy is allocated to that site for the gap.
- Incomplete PowerTrack half-hours: skipped and treated as 0 kWh.
- Generation timestamps: treated as interval-beginning so the file tiles June exactly.
- TOU bucket: chosen from the SAST interval start time.
- Wheeling cost: charged on allocated energy at the configured rate.
