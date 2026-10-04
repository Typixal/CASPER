"""Tests for turning raw k6 output into the comparison.

Fixtures are REAL k6 v2.3.0 output (a 6-second run against a local stub
with a ~10% 503 rate), trimmed -- not hand-written guesses at the format.
"""

import json
from pathlib import Path

import pytest

import compare

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def k6_summary():
    return json.loads((FIXTURES / "k6_summary.json").read_text(encoding="utf-8"))


def test_summarize_reads_request_count_and_latency(k6_summary):
    summary = compare.summarize_k6(k6_summary)

    assert summary["requests"] == 74
    assert summary["p95_ms"] == pytest.approx(76.41, abs=0.01)
    assert summary["median_ms"] == pytest.approx(47.66, abs=0.01)


def test_summarize_reads_the_failure_rate_not_the_misleading_passes_field(k6_summary):
    # In k6's http_req_failed, "passes" counts requests that FAILED (6 here)
    # and "fails" counts ones that succeeded (68). Reading "passes" as
    # successes would invert the headline result of the whole project.
    summary = compare.summarize_k6(k6_summary)

    assert summary["error_rate"] == pytest.approx(6 / 74)
    assert summary["success_pct"] == pytest.approx(68 / 74 * 100)


def test_summarize_treats_missing_dropped_iterations_as_zero(k6_summary):
    # k6 omits the metric entirely when nothing was dropped.
    assert compare.summarize_k6(k6_summary)["dropped"] == 0


def test_summarize_counts_dropped_iterations_when_k6_reports_them(k6_summary):
    # Dropped = k6 could not even start a request on schedule; for an
    # arrival-rate test those are candidates who never got through.
    k6_summary["metrics"]["dropped_iterations"] = {"values": {"count": 12, "rate": 2.0}}

    assert compare.summarize_k6(k6_summary)["dropped"] == 12


def test_success_pct_counts_dropped_requests_as_unsuccessful(k6_summary):
    # 74 sent (68 OK) plus 26 k6 could not even send = 100 attempts, 68 good.
    # Leaving the 26 out would flatter whichever strategy was MORE overloaded.
    k6_summary["metrics"]["dropped_iterations"] = {"values": {"count": 26, "rate": 4.0}}

    assert compare.summarize_k6(k6_summary)["success_pct"] == pytest.approx(68.0)


# --- time series from raw k6 samples (pandas) -------------------------------


def test_timeseries_accounts_for_every_request():
    series = compare.timeseries(FIXTURES / "k6_samples.csv", bucket_s=2)

    assert sum(b["requests"] for b in series["buckets"]) == 74


def test_timeseries_accounts_for_every_failure():
    series = compare.timeseries(FIXTURES / "k6_samples.csv", bucket_s=2)

    failures = sum(round(b["error_rate"] * b["requests"]) for b in series["buckets"])
    assert failures == 6


def test_timeseries_buckets_are_relative_to_the_first_sample():
    series = compare.timeseries(FIXTURES / "k6_samples.csv", bucket_s=2)

    offsets = [b["t"] for b in series["buckets"]]
    assert offsets[0] == 0
    assert all(later - earlier == 2 for earlier, later in zip(offsets, offsets[1:]))


def test_timeseries_reports_the_runs_start_time_for_aligning_scale_events():
    series = compare.timeseries(FIXTURES / "k6_samples.csv", bucket_s=2)

    # Unix seconds of the first sample in the fixture.
    assert series["start"] == 1791120228


def test_timeseries_p95_never_exceeds_the_slowest_sample():
    series = compare.timeseries(FIXTURES / "k6_samples.csv", bucket_s=2)

    assert max(b["p95_ms"] for b in series["buckets"]) <= 78.56


# --- scale events from Module C's audit log ----------------------------------


def write_log(tmp_path, entries):
    path = tmp_path / "scale_actions.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


def entry(iso, healthy, source):
    return {
        "timestamp": iso,
        "action": "scale_to",
        "requested_replicas": healthy,
        "actual_healthy_replicas": healthy,
        "replica_names": [],
        "source": source,
    }


# 1791120228 == 2026-10-04T13:23:48Z, the fixture run's start
RUN_START = 1791120228


def test_scale_events_are_placed_relative_to_the_run_start(tmp_path):
    log = write_log(tmp_path, [entry("2026-10-04T13:24:18+00:00", 3, "reactive")])

    events = compare.scale_events(log, start=RUN_START, end=RUN_START + 60, sources={"reactive"})

    assert events == [{"t": 30.0, "replicas": 3, "source": "reactive"}]


def test_scale_events_outside_the_run_window_are_ignored(tmp_path):
    log = write_log(
        tmp_path,
        [
            entry("2026-10-04T13:20:00+00:00", 5, "reactive"),  # before
            entry("2026-10-04T13:30:00+00:00", 5, "reactive"),  # after
        ],
    )

    assert compare.scale_events(log, RUN_START, RUN_START + 60, {"reactive"}) == []


def test_scale_events_keep_only_the_requested_sources(tmp_path):
    log = write_log(
        tmp_path,
        [
            entry("2026-10-04T13:24:00+00:00", 2, "manual"),
            entry("2026-10-04T13:24:10+00:00", 4, "predictive"),
        ],
    )

    events = compare.scale_events(log, RUN_START, RUN_START + 60, {"predictive"})
    assert [e["source"] for e in events] == ["predictive"]


def test_replica_seconds_integrates_the_replica_count_over_the_run():
    # 1 replica for 10 s, then 3 replicas for the remaining 20 s = 70.
    events = [{"t": 10.0, "replicas": 3, "source": "reactive"}]

    assert compare.replica_seconds(events, initial=1, duration_s=30) == 70.0


def test_replica_seconds_with_no_scaling_is_initial_times_duration():
    assert compare.replica_seconds([], initial=2, duration_s=30) == 60.0


# --- the verdict and the reports ---------------------------------------------


def run_result(p95, error_rate, success_pct, replica_secs):
    return {
        "summary": {
            "requests": 1000,
            "median_ms": p95 / 2,
            "p95_ms": p95,
            "avg_ms": p95 / 2,
            "max_ms": p95 * 2,
            "error_rate": error_rate,
            "success_pct": success_pct,
            "dropped": 0,
        },
        "replica_seconds": replica_secs,
        "events": [],
        "series": {"start": 0, "buckets": []},
    }


@pytest.fixture
def runs():
    return {
        "reactive": run_result(p95=1800.0, error_rate=0.12, success_pct=88.0, replica_secs=500.0),
        "predictive": run_result(p95=150.0, error_rate=0.0, success_pct=100.0, replica_secs=700.0),
    }


def test_the_verdict_picks_the_better_strategy_per_metric(runs):
    verdict = compare.build_comparison(runs)["verdict"]

    assert verdict["p95_ms"] == "predictive"        # lower is better
    assert verdict["error_rate"] == "predictive"    # lower is better
    assert verdict["success_pct"] == "predictive"   # higher is better


def test_the_verdict_credits_reactive_when_it_uses_less_capacity(runs):
    # The honest trade-off: provisioning ahead of traffic costs replica-time.
    assert compare.build_comparison(runs)["verdict"]["replica_seconds"] == "reactive"


def test_equal_results_are_reported_as_a_tie(runs):
    runs["predictive"]["summary"]["error_rate"] = runs["reactive"]["summary"]["error_rate"]

    assert compare.build_comparison(runs)["verdict"]["error_rate"] == "tie"


def test_the_comparison_reports_the_p95_reduction(runs):
    # (1800 - 150) / 1800 = 91.67 %
    assert compare.build_comparison(runs)["p95_reduction_pct"] == pytest.approx(91.67, abs=0.01)


def test_write_reports_saves_json_that_round_trips(tmp_path, runs):
    comparison = compare.build_comparison(runs)

    compare.write_reports(comparison, tmp_path)

    saved = json.loads((tmp_path / "comparison.json").read_text(encoding="utf-8"))
    assert saved == comparison


def test_write_reports_saves_a_markdown_table_for_the_report(tmp_path, runs):
    compare.write_reports(compare.build_comparison(runs), tmp_path)

    markdown = (tmp_path / "comparison.md").read_text(encoding="utf-8")
    assert "| p95 response time" in markdown
    assert "1800" in markdown and "150" in markdown
