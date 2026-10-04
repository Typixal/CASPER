"""Turn raw k6 output and the audit log into the reactive-vs-predictive comparison."""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from probe import percentile


def summarize_k6(summary):
    """Extract headline numbers from a k6 handleSummary() document.

    Args:
        summary: Parsed k6 summary JSON.

    Returns:
        Dict with requests, median/p95/avg/max latency, error_rate,
        success_pct and dropped.
    """
    metrics = summary["metrics"]
    duration = metrics["http_req_duration"]["values"]
    # http_req_failed is a rate over "request failed", so its `passes` counts
    # failures. `rate` avoids the inverted naming.
    error_rate = metrics["http_req_failed"]["values"]["rate"]
    dropped = metrics.get("dropped_iterations", {}).get("values", {}).get("count", 0)
    requests = metrics["http_reqs"]["values"]["count"]

    # Dropped iterations count as attempts; leaving them out flatters the
    # more overloaded run.
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
    """Bucket a k6 CSV export into per-interval p95 and error rate.

    Args:
        csv_path: k6 `--out csv` file.
        bucket_s: Bucket width in seconds.

    Returns:
        {"start": unix seconds of the first sample, "buckets": [...]}. Each
        bucket is {"t", "requests", "p95_ms", "error_rate"} with t relative to
        start. Buckets are contiguous; an empty one has p95_ms None, not 0.
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
    """Read one run's scale actions from Module C's audit log.

    Args:
        log_path: scale_actions.jsonl; a missing file yields no events.
        start: Window start, unix seconds.
        end: Window end, unix seconds.
        sources: Sources to keep, e.g. {"reactive"}.

    Returns:
        [{"t", "replicas", "source"}] with t relative to start and replicas
        the count that actually came up healthy.
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
    """Area under the replica-count step function, as a cost proxy.

    Args:
        events: Scale events from scale_events().
        initial: Replicas at t=0.
        duration_s: Run length.

    Returns:
        Total replica-seconds.
    """
    total = 0.0
    current, since = initial, 0.0
    for event in sorted(events, key=lambda e: e["t"]):
        total += current * (event["t"] - since)
        current, since = event["replicas"], event["t"]
    total += current * (duration_s - since)
    return total


# metric -> whether a higher value is better
_METRICS = {
    "p95_ms": False,
    "error_rate": False,
    "success_pct": True,
    "replica_seconds": False,
}


def _value(run, metric):
    """Read one comparison metric from a run."""
    if metric == "replica_seconds":
        return run["replica_seconds"]
    return run["summary"][metric]


def build_comparison(runs):
    """Compare the two runs metric by metric.

    Args:
        runs: {"reactive": run, "predictive": run}, each with "summary",
            "replica_seconds", "events" and "series".

    Returns:
        Dict with the runs ("strategies"), a per-metric "verdict" and
        "p95_reduction_pct".
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
    """Write comparison.json and the markdown table comparison.md.

    Args:
        comparison: Output of build_comparison().
        out_dir: Folder to write into; created if missing.

    Returns:
        The output folder.
    """
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
