import csv

COLUMNS = [
    "site",
    "meter",
    "tou_bucket",
    "consumption_kwh",
    "allocated_kwh",
    "residual_kwh",
    "wheeling_zar",
]


def write_data_quality_report(path, issues):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# Data Quality Report\n\n")
        handle.write("Findings recorded while normalising the three input files.\n\n")

        sources = []
        for source, _ in issues:
            if source not in sources:
                sources.append(source)

        for source in sources:
            handle.write(f"## {source}\n\n")
            for issue_source, message in issues:
                if issue_source == source:
                    handle.write(f"- {message}\n")
            handle.write("\n")

        handle.write("## Decisions\n\n")
        handle.write("- Duplicate timestamps: the last value in the file is kept.\n")
        handle.write("- Missing consumption intervals: treated as 0 kWh, so no energy is allocated to that site for the gap.\n")
        handle.write("- Incomplete PowerTrack half-hours: skipped and treated as 0 kWh.\n")
        handle.write("- Generation timestamps: treated as interval-beginning so the file tiles June exactly.\n")
        handle.write("- TOU bucket: chosen from the SAST interval start time.\n")
        handle.write("- Wheeling cost: charged on allocated energy at the configured rate.\n")


def write_monthly_summary_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "site": row["site"],
                "meter": row["meter"],
                "tou_bucket": row["tou_bucket"],
                "consumption_kwh": f"{row['consumption_kwh']:.3f}",
                "allocated_kwh": f"{row['allocated_kwh']:.3f}",
                "residual_kwh": f"{row['residual_kwh']:.3f}",
                "wheeling_zar": f"{row['wheeling_zar']:.2f}",
            })


def write_monthly_summary_md(path, rows, unallocated):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# Monthly Summary - June 2026\n\n")
        handle.write("| Site | Meter | TOU bucket | Consumption kWh | Allocated kWh | Residual kWh | Wheeling ZAR |\n")
        handle.write("|---|---|---|---:|---:|---:|---:|\n")
        for row in rows:
            handle.write(
                f"| {row['site']} | {row['meter']} | {row['tou_bucket']} | "
                f"{row['consumption_kwh']:.3f} | {row['allocated_kwh']:.3f} | "
                f"{row['residual_kwh']:.3f} | {row['wheeling_zar']:.2f} |\n"
            )
        handle.write(f"\n**Total unallocated generation: {unallocated:.3f} kWh**\n")
