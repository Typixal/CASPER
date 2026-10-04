"""Module D -- turn raw k6 output into the reactive-vs-predictive comparison.

The three headline metrics are the ones the project committed to in its
needs metrics: response time, error rate, and % successful requests.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from probe import percentile


def summarize_k6(summary):
    """Headline numbers from a k6 handleSummary() JSON document.

    Note on http_req_failed: it is a k6 "rate" metric over a boolean that is
    true when a request FAILED. So its `passes` field counts failures and
    `fails` counts successes. Reading the `rate` (share of requests that
    failed) sidesteps that inverted naming entirely.
    """
    metrics = summary["metrics"]
    duration = metrics["http_req_duration"]["values"]
    error_rate = metrics["http_req_failed"]["values"]["rate"]
    dropped = metrics.get("dropped_iterations", {}).get("values", {}).get("count", 0)
    requests = metrics["http_reqs"]["values"]["count"]

    # Success is measured against every candidate who TRIED, including the
    # ones k6 could not even send on schedule (dropped). Leaving them out
    # would flatter whichever strategy was more overloaded.
    succeeded = requests * (1.0 - error_rate)
    attempted = requests + dropped

    return {
        "requests": requests,
        "median_ms": duration["med"],
        "p95_ms": duration["p(95)"],
        "avg_ms": duration["avg"],
        "max_ms": duration["max"],
        "error_rate": error_rate,
        "success_pct": (succeeded / attempted * 100.0) if attempted else 0.0,
        "dropped": dropped,
    }


def timeseries(csv_path, bucket_s=5):
    """Bucket a k6 CSV export into per-interval latency and error rate.

    This is what shows WHEN each strategy hurt: an aggregate p95 hides
    whether the pain was a ten-second blip or the whole ramp.

    Returns {"start": unix seconds of the first sample, "buckets": [...]},
    each bucket {"t", "requests", "p95_ms", "error_rate"}, with t in seconds
    from the start. Buckets are contiguous; an interval with no requests has
    p95_ms None rather than a misleading 0 ms.
    """
    raw = pd.read_csv(csv_path, usecols=["metric_name", "timestamp", "metric_value"])
    start = int(raw["timestamp"].min())
    raw["bucket"] = (raw["timestamp"] - start) // bucket_s

    durations = raw[raw["metric_name"] == "http_req_duration"]
    failed = raw[raw["metric_name"] == "http_req_failed"]

    last = int(raw["bucket"].max())
    buckets = []
    for b in range(last + 1):
        in_bucket = durations[durations["bucket"] == b]["metric_value"].tolist()
        fail_flags = failed[failed["bucket"] == b]["metric_value"]
        buckets.append(
            {
                "t": b * bucket_s,
                "requests": len(in_bucket),
                "p95_ms": percentile(in_bucket, 95) if in_bucket else None,
                "error_rate": float(fail_flags.mean()) if len(fail_flags) else 0.0,
            }
        )

    return {"start": start, "buckets": buckets}


def scale_events(log_path, start, end, sources):
    """Scale actions from Module C's audit log inside one run's window.

    Returns [{"t", "replicas", "source"}] with t in seconds from `start`
    (unix seconds) and replicas = how many ACTUALLY came up healthy, which is
    what served traffic -- not what was requested.
    """
    events = []
    path = Path(log_path)
    if not path.exists():
        return events

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("source") not in sources:
            continue
        at = datetime.fromisoformat(record["timestamp"]).timestamp()
        if start <= at <= end:
            events.append(
                {
                    "t": round(at - start, 3),
                    "replicas": record["actual_healthy_replicas"],
                    "source": record["source"],
                }
            )
    return events


def replica_seconds(events, initial, duration_s):
    """Area under the replica-count step function: a cost proxy.

    Predictive scaling wins on latency by provisioning BEFORE the traffic,
    which means paying for capacity that sits idle for a while. Reporting
    replica-seconds keeps the comparison honest about that trade-off.
    """
    total = 0.0
    current, since = initial, 0.0
    for event in sorted(events, key=lambda e: e["t"]):
        total += current * (event["t"] - since)
        current, since = event["replicas"], event["t"]
    total += current * (duration_s - since)
    return total


# metric -> True when a HIGHER value is better
_METRICS = {
    "p95_ms": False,
    "error_rate": False,
    "success_pct": True,
    "replica_seconds": False,
}


def _value(run, metric):
    if metric == "replica_seconds":
        return run["replica_seconds"]
    return run["summary"][metric]


def build_comparison(runs):
    """Reactive vs predictive: both runs, a per-metric verdict, headline deltas.

    `runs` is {"reactive": {...}, "predictive": {...}}, each with "summary"
    (summarize_k6), "replica_seconds", "events" and "series".
    """
    reactive, predictive = runs["reactive"], runs["predictive"]

    verdict = {}
    for metric, higher_is_better in _METRICS.items():
        r, p = _value(reactive, metric), _value(predictive, metric)
        if r == p:
            verdict[metric] = "tie"
        elif (p > r) == higher_is_better:
            verdict[metric] = "predictive"
        else:
            verdict[metric] = "reactive"

    r_p95 = reactive["summary"]["p95_ms"]
    reduction = (r_p95 - predictive["summary"]["p95_ms"]) / r_p95 * 100.0 if r_p95 else 0.0

    return {
        "strategies": runs,
        "verdict": verdict,
        "p95_reduction_pct": round(reduction, 2),
    }


def write_reports(comparison, out_dir):
    """Write comparison.json (machine-readable) and comparison.md (for the report)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    r = comparison["strategies"]["reactive"]
    p = comparison["strategies"]["predictive"]
    v = comparison["verdict"]
    rows = [
        ("p95 response time (ms)", "{:.0f}".format(r["summary"]["p95_ms"]),
         "{:.0f}".format(p["summary"]["p95_ms"]), v["p95_ms"]),
        ("median response time (ms)", "{:.0f}".format(r["summary"]["median_ms"]),
         "{:.0f}".format(p["summary"]["median_ms"]), "-"),
        ("error rate", "{:.2%}".format(r["summary"]["error_rate"]),
         "{:.2%}".format(p["summary"]["error_rate"]), v["error_rate"]),
        ("% successful requests", "{:.2f}%".format(r["summary"]["success_pct"]),
         "{:.2f}%".format(p["summary"]["success_pct"]), v["success_pct"]),
        ("requests sent", str(r["summary"]["requests"]), str(p["summary"]["requests"]), "-"),
        ("dropped (never sent)", str(r["summary"]["dropped"]), str(p["summary"]["dropped"]), "-"),
        ("replica-seconds (cost)", "{:.0f}".format(r["replica_seconds"]),
         "{:.0f}".format(p["replica_seconds"]), v["replica_seconds"]),
    ]

    lines = [
        "# CASPER - reactive vs predictive",
        "",
        "Same traffic curve, same infrastructure, same scale controller -- only",
        "the scaling strategy differs.",
        "",
        "| Metric | Reactive | Predictive (CASPER) | Better |",
        "|---|---|---|---|",
    ]
    lines += ["| {} | {} | {} | {} |".format(*row) for row in rows]
    lines += [
        "",
        "p95 reduction with CASPER: **{:.1f}%**".format(comparison["p95_reduction_pct"]),
        "",
        "Replica-seconds is the honest cost of predicting: CASPER provisions",
        "before the traffic arrives, so some of that capacity sits idle first.",
        "",
    ]
    (out / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    return out
