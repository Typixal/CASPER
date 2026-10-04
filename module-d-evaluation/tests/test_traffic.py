"""Tests for the exam-result-day traffic curve both runs share."""

import json

import traffic


def test_the_curve_starts_quiet_well_below_peak():
    config = traffic.k6_config(peak_rps=250)

    assert config["startRate"] < 250 * 0.1


def test_the_curve_reaches_the_peak_rate():
    config = traffic.k6_config(peak_rps=250)

    assert max(stage["target"] for stage in config["stages"]) == 250


def test_the_curve_decays_after_the_peak():
    config = traffic.k6_config(peak_rps=250)

    assert config["stages"][-1]["target"] < 250


def test_the_ramp_starts_after_the_quiet_period():
    # The predictive policy schedules its scale-up against this offset, so it
    # has to be exactly where the k6 ramp begins.
    config = traffic.k6_config(peak_rps=250)
    first = config["stages"][0]

    assert first["target"] == config["startRate"]  # quiet hold
    assert traffic.RAMP_START_S == int(first["duration"].rstrip("s"))


def test_total_duration_is_the_sum_of_the_stages():
    config = traffic.k6_config(peak_rps=250)

    total = sum(int(stage["duration"].rstrip("s")) for stage in config["stages"])
    assert total == traffic.TOTAL_S


def test_replicas_needed_uses_the_documented_conversion_and_rounds_up():
    # Same rule as Module B: demand / per-replica capacity, always rounded up.
    assert traffic.replicas_needed(peak_rps=250, per_replica_rps=4000 / 60) == 4


def test_replicas_needed_is_never_zero():
    assert traffic.replicas_needed(peak_rps=1, per_replica_rps=66.7) == 1


def test_write_k6_config_produces_json_k6_can_read(tmp_path):
    path = traffic.write_k6_config(tmp_path / "stages.json", peak_rps=250)

    assert json.loads(path.read_text(encoding="utf-8")) == traffic.k6_config(peak_rps=250)
