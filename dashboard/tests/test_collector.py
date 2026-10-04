"""Tests for the dashboard reading Module D's comparison results."""

import json

import pytest

import collector


@pytest.fixture
def module_d(tmp_path, monkeypatch):
    """Point the collector at a temporary module-d-evaluation folder."""
    results = tmp_path / "results"
    k6 = tmp_path / "k6"
    results.mkdir()
    k6.mkdir()
    monkeypatch.setattr(collector, "MODULE_D_RESULTS_DIR", results)
    monkeypatch.setattr(collector, "MODULE_D_K6_DIR", k6)
    return results


def strategy(p95, error_rate, success_pct, replica_seconds):
    return {
        "summary": {"p95_ms": p95, "error_rate": error_rate, "success_pct": success_pct,
                    "median_ms": 1.0, "requests": 1, "dropped": 0},
        "replica_seconds": replica_seconds,
        "events": [],
        "series": {"start": 0, "buckets": []},
    }


def write_comparison(results):
    (results / "comparison.json").write_text(json.dumps({
        "strategies": {
            "reactive": strategy(1800.0, 0.12, 88.0, 500.0),
            "predictive": strategy(150.0, 0.0, 100.0, 700.0),
        },
        "verdict": {"p95_ms": "predictive", "error_rate": "predictive",
                    "success_pct": "predictive", "replica_seconds": "reactive"},
        "p95_reduction_pct": 91.67,
    }), encoding="utf-8")


def test_module_d_exposes_the_headline_numbers_per_strategy(module_d):
    write_comparison(module_d)

    comparison = collector.read_other_modules()["d"]["comparison"]

    assert comparison["reactive"]["p95_ms"] == 1800.0
    assert comparison["predictive"]["success_pct"] == 100.0
    assert comparison["p95_reduction_pct"] == 91.67


def test_module_d_exposes_the_verdict(module_d):
    write_comparison(module_d)

    assert collector.read_other_modules()["d"]["comparison"]["verdict"]["replica_seconds"] == "reactive"


def test_module_d_without_results_has_no_comparison(module_d):
    assert collector.read_other_modules()["d"]["comparison"] is None


def test_a_corrupt_comparison_file_does_not_break_the_dashboard(module_d):
    (module_d / "comparison.json").write_text("{not json", encoding="utf-8")

    assert collector.read_other_modules()["d"]["comparison"] is None
