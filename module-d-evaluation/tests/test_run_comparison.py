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
        self.max_replicas = {}

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += timedelta(seconds=seconds)

    def reset(self, replicas):
        self.calls.append(("reset", replicas))

    def start_strategy(self, name, prediction_path, max_replicas):
        self.calls.append(("start", name))
        self.max_replicas[name] = max_replicas
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


def test_the_reactive_ceiling_stays_at_six_for_the_default_load():
    # 250 req/s needs 4 replicas; the reactive scaler keeps its usual
    # ceiling of 6, so the committed results stay reproducible.
    assert rc.make_plan(peak_rps=250).reactive_max == 6


def test_the_reactive_ceiling_rises_to_match_casper_under_heavier_load():
    # 500 req/s needs 8 replicas. Capping reactive at 6 while CASPER gets 8
    # would make reactive lose because of its ceiling, not because it reacts
    # late -- the experiment would prove nothing.
    plan = rc.make_plan(peak_rps=500, per_replica_rps=4000 / 60)

    assert plan.predictive_peak == 8
    assert plan.reactive_max == 8


def test_the_reactive_scaler_is_started_with_the_plans_ceiling(tmp_path):
    env = RecordingEnv()
    plan = rc.make_plan(peak_rps=500)

    rc.run(env, plan, tmp_path)

    assert env.max_replicas["reactive"] == plan.reactive_max


def test_the_reactive_command_passes_the_ceiling_to_the_scaler():
    command = rc.reactive_command("python.exe", 8)

    assert command[-2:] == ["--max", "8"]
    assert command[1].endswith("reactive_baseline.py")


def test_dry_run_states_both_ceilings():
    text = rc.describe(rc.make_plan(peak_rps=500))

    assert "8 replicas" in text
    assert "up to 8" in text


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


def test_the_window_is_not_held_open_by_default():
    # run-demo.ps1 runs a --dry-run inline in ITS OWN console before
    # launching the real run. Holding there would block the launcher on an
    # "Press Enter" prompt nobody asked for.
    assert rc.should_hold_window(["--dry-run"]) is False
    assert rc.should_hold_window([]) is False


def test_the_window_is_held_open_only_when_asked():
    # The launcher passes --hold to the real run it starts in a new window,
    # so the result (or the error) stays on screen.
    assert rc.should_hold_window(["--hold"]) is True
