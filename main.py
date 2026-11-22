import argparse
import json
from pathlib import Path

from etana.allocation import allocate
from etana.normalise import (
    load_generation,
    load_meterflow,
    load_powertrack,
    month_starts_sast,
    month_starts_utc,
)
from etana.reports import (
    write_data_quality_report,
    write_monthly_summary_csv,
    write_monthly_summary_md,
)


def load_config(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main():
    parser = argparse.ArgumentParser(description="Etana Energy June 2026 allocation")
    parser.add_argument("--data-dir", default="candidate_pack/data")
    parser.add_argument("--out-dir", default="outputs")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(data_dir / "allocation_config.json")
    starts = month_starts_utc(config["billing_month"])
    sast_starts = month_starts_sast(config["billing_month"])

    issues = []
    meterflow, found = load_meterflow(data_dir / "meterflow_2026-06.csv", starts)
    issues += found
    powertrack, found = load_powertrack(data_dir / "powertrack_2026-06.csv", sast_starts)
    issues += found
    generation, found = load_generation(
        data_dir / "riverside_hydro_generation_2026-06.csv", starts
    )
    issues += found

    consumption = {}
    consumption.update(meterflow)
    consumption.update(powertrack)

    rows, unallocated = allocate(config, generation, consumption, starts)

    write_data_quality_report(out_dir / "data_quality_report.md", issues)
    write_monthly_summary_csv(out_dir / "monthly_summary.csv", rows)
    write_monthly_summary_md(out_dir / "monthly_summary.md", rows, unallocated)

    print(f"Wrote reports to {out_dir}")
    print(f"Total unallocated generation: {unallocated:.3f} kWh")


if __name__ == "__main__":
    main()
