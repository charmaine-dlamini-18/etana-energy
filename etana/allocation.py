from datetime import time

from .normalise import SAST

BUCKETS = ["peak", "standard", "offpeak"]


def classify_tou(start_utc):
    local = start_utc.astimezone(SAST)
    if local.weekday() >= 5:
        return "offpeak"
    moment = local.time()
    if (time(7, 0) <= moment < time(10, 0)) or (time(18, 0) <= moment < time(20, 0)):
        return "peak"
    if (time(6, 0) <= moment < time(7, 0)) or (time(10, 0) <= moment < time(18, 0)) or (time(20, 0) <= moment < time(22, 0)):
        return "standard"
    return "offpeak"


def allocate(config, generation, consumption, starts):
    rates = config["wheeling_rates_zar_per_kwh"]
    totals = {}
    for site in config["sites"]:
        for bucket in BUCKETS:
            totals[(site["site"], bucket)] = {"consumption": 0.0, "allocated": 0.0}

    unallocated = 0.0
    for start in starts:
        generated = generation.get(start, 0.0)
        bucket = classify_tou(start)
        for site in config["sites"]:
            share = site["allocation_pct"] / 100.0
            used = consumption.get((site["meter"], start), 0.0)
            target = share * generated
            allocated = min(target, used)
            unallocated += target - allocated
            row = totals[(site["site"], bucket)]
            row["consumption"] += used
            row["allocated"] += allocated

    rows = []
    for site in config["sites"]:
        for bucket in BUCKETS:
            values = totals[(site["site"], bucket)]
            allocated = values["allocated"]
            rows.append({
                "site": site["site"],
                "meter": site["meter"],
                "tou_bucket": bucket,
                "consumption_kwh": values["consumption"],
                "allocated_kwh": allocated,
                "residual_kwh": values["consumption"] - allocated,
                "wheeling_zar": allocated * rates[bucket],
            })
    return rows, unallocated
