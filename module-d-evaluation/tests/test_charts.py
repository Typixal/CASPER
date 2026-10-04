"""Tests for the comparison charts used in the Phase I report."""

import charts
import compare

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def run_with_series(p95s, replicas_events):
    return {
        "summary": {
            "requests": 100, "median_ms": 50.0, "p95_ms": max(p95s), "avg_ms": 60.0,
            "max_ms": max(p95s), "error_rate": 0.05, "success_pct": 95.0, "dropped": 0,
        },
        "replica_seconds": 100.0,
        "events": replicas_events,
        "series": {
            "start": 0,
            "buckets": [
                {"t": i * 5, "requests": 10, "p95_ms": v, "error_rate": 0.0}
                for i, v in enumerate(p95s)
            ],
        },
    }


def comparison():
    return compare.build_comparison(
        {
            "reactive": run_with_series(
                [80, 900, 1800, 400, 90], [{"t": 12.0, "replicas": 3, "source": "reactive"}]
            ),
            "predictive": run_with_series(
                [70, 110, 120, 100, 80], [{"t": 2.0, "replicas": 4, "source": "predictive"}]
            ),
        }
    )


def test_render_writes_the_latency_over_time_chart(tmp_path):
    written = charts.render(comparison(), tmp_path, ramp_start_s=5, initial_replicas=1)

    latency = tmp_path / "latency_over_time.png"
    assert latency in written
    assert latency.read_bytes().startswith(PNG_SIGNATURE)


def test_render_writes_the_summary_bars_chart(tmp_path):
    charts.render(comparison(), tmp_path, ramp_start_s=5, initial_replicas=1)

    assert (tmp_path / "summary_bars.png").read_bytes().startswith(PNG_SIGNATURE)


def test_render_copes_with_empty_buckets(tmp_path):
    # Empty intervals (p95_ms None) are skipped, not plotted as 0 ms.
    data = comparison()
    data["strategies"]["reactive"]["series"]["buckets"][2]["p95_ms"] = None

    charts.render(data, tmp_path, ramp_start_s=5, initial_replicas=1)

    assert (tmp_path / "latency_over_time.png").stat().st_size > 0
