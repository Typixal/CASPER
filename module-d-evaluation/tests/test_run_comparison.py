"""Tests for the comparison orchestrator's sequencing.

The real environment drives Docker, k6 and two scaling processes. Here a
recording environment stands in for those side effects -- it is not a mock of
the code under test, it is the boundary the orchestrator is designed to be
handed. k6 output it "produces" is the REAL k6 fixture, so the comparison
pipeline downstream runs on genuine data.
"""

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import run_comparison as rc

FIXTURES = Path(__file__).resolve().parent / "fixtures"
T0 = datetime(2026, 10, 4, 13, 23, 48, tzinfo=timezone.utc)  # fixture start


class RecordingEnv:
    """Records what the orchestrator asked for; writes real k6 fixtures."""

    def __init__(self, k6_fails_for=None):
        self.calls = []
        self.t = T0
        self.k6_fails_for = k6_fails_for
        self.predictions = {}

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += timedelta(seconds=seconds)

    def reset(self, replicas):
        self.calls.append(("reset", replicas))

    def start_strategy(self, name, prediction_path):
        self.calls.append(("start", name))
        if prediction_path is not None:
            self.predictions[name] = json.loads(Path(prediction_path).read_text(encoding="utf-8"))
        return name

    def stop_strategy(self, handle):
        self.calls.append(("stop", handle))

    def run_k6(self, strategy, stages_path, summary_path, csv_path):
        self.calls.append(("k6", strategy))
        if strategy == self.k6_fails_for:
            raise RuntimeError("k6 crashed")
        shutil.copy(FIXTURES / "k6_summary.json", summary_path)
        shutil.copy(FIXTURES / "k6_samples.csv", csv_path)

    def audit_log(self):
        return FIXTURES / "does_not_exist.jsonl"


def test_the_reactive_run_happens_first_then_the_predictive_run(tmp_path):
    env = RecordingEnv()

    rc.run(env, rc.make_plan(), tmp_path)

    order = [name for kind, name in env.calls if kind == "k6"]
    assert order == ["reactive", "predictive"]


def test_every_run_starts_from_the_same_baseline(tmp_path):
    # Same starting capacity for both strategies is part of the experimental
    # control -- otherwise the second run inherits the first run's replicas.
    env = RecordingEnv()
    plan = rc.make_plan(baseline_replicas=1)

    rc.run(env, plan, tmp_path)

    kinds = [kind for kind, _ in env.calls]
    assert kinds.count("reset") >= 2
    for index, (kind, _) in enumerate(env.calls):
        if kind == "start":
            assert env.calls[index - 1] == ("reset", 1)


def test_the_predictive_run_is_given_a_prediction_and_the_reactive_run_is_not(tmp_path):
    env = RecordingEnv()

    rc.run(env, rc.make_plan(), tmp_path)

    assert "predictive" in env.predictions
    assert "reactive" not in env.predictions


def test_the_prediction_uses_the_frozen_schema(tmp_path):
    env = RecordingEnv()

    rc.run(env, rc.make_plan(), tmp_path)

    assert set(env.predictions["predictive"]) == {
        "event_id", "predicted_peak_replicas", "ramp_start", "ramp_peak", "ramp_end",
    }


def test_the_prediction_scales_up_ahead_of_the_traffic_ramp(tmp_path):
    env = RecordingEnv()
    plan = rc.make_plan(lead_s=20)

    rc.run(env, plan, tmp_path)

    prediction = env.predictions["predictive"]
    ramp_start = datetime.fromisoformat(prediction["ramp_start"])
    k6_ramp = datetime.fromisoformat(prediction["ramp_peak"]) - timedelta(seconds=rc.traffic.RAMP_S)
    assert (k6_ramp - ramp_start).total_seconds() == pytest.approx(20)


def test_the_prediction_asks_for_enough_replicas_for_the_peak(tmp_path):
    env = RecordingEnv()

    rc.run(env, rc.make_plan(peak_rps=250, per_replica_rps=4000 / 60), tmp_path)

    assert env.predictions["predictive"]["predicted_peak_replicas"] == 4


def test_a_strategy_is_stopped_even_when_k6_fails(tmp_path):
    # Cleanup is not optional: a crashed k6 must not leave a scaling process
    # running in the background, quietly resizing the stack.
    env = RecordingEnv(k6_fails_for="reactive")

    with pytest.raises(RuntimeError):
        rc.run(env, rc.make_plan(), tmp_path)

    assert ("stop", "reactive") in env.calls


def test_a_full_run_writes_the_reports_and_charts(tmp_path):
    rc.run(RecordingEnv(), rc.make_plan(), tmp_path)

    for name in ("comparison.json", "comparison.md", "latency_over_time.png", "summary_bars.png"):
        assert (tmp_path / name).is_file(), name


def test_dry_run_describes_the_plan_without_touching_anything():
    text = rc.describe(rc.make_plan(peak_rps=250))

    assert "250" in text
    assert "reactive" in text and "predictive" in text
