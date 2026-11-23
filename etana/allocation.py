from datetime import time

from .normalise import SAST

# Time-of-use categories used for reporting and pricing.
BUCKETS = ["peak", "standard", "offpeak"]


def classify_tou(start_utc):
    # Convert the interval start to local South African time.
    local = start_utc.astimezone(SAST)
    # Weekends are always off-peak.
    if local.weekday() >= 5:
        return "offpeak"
    moment = local.time()
    # Morning and evening peak windows.
    if (time(7, 0) <= moment < time(10, 0)) or (time(18, 0) <= moment < time(20, 0)):
        return "peak"
    # Standard windows around the peaks.
    if (time(6, 0) <= moment < time(7, 0)) or (time(10, 0) <= moment < time(18, 0)) or (time(20, 0) <= moment < time(22, 0)):
        return "standard"
    # Everything else is off-peak.
    return "offpeak"


def allocate(config, generation, consumption, starts):
    # Wheeling rates per bucket from config.
    rates = config["wheeling_rates_zar_per_kwh"]

    # Running totals per site and bucket.
    totals = {}
    for site in config["sites"]:
        for bucket in BUCKETS:
            totals[(site["site"], bucket)] = {"consumption": 0.0, "allocated": 0.0}

    unallocated = 0.0
    for start in starts:
        # Generation for this interval (0 if missing).
        generated = generation.get(start, 0.0)
        bucket = classify_tou(start)
        for site in config["sites"]:
            # Each site's share of generation.
            share = site["allocation_pct"] / 100.0
            # Consumption for this site at this interval.
            used = consumption.get((site["meter"], start), 0.0)
            target = share * generated
            # Cannot allocate more than was actually consumed.
            allocated = min(target, used)
            # Any shortfall is left unallocated.
            unallocated += target - allocated
            row = totals[(site["site"], bucket)]
            row["consumption"] += used
            row["allocated"] += allocated

    # Build one output row per site and bucket.
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
