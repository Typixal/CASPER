"""Tests for the event schedule: Module A's events joined with Module B's
predictions, so a viewer sees what is coming, how big it is, and what CASPER
will do about it."""

import json
from datetime import datetime, timezone

import pytest

import collector

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def event(event_id, date, candidates=1000):
    return {
        "event_id": event_id,
        "board": "CBSE",
        "event_type": "exam_result",
        "date": date,
        "registered_candidates": candidates,
        "prior_similar_event_ids": [],
    }


@pytest.fixture
def modules(tmp_path, monkeypatch):
    events = tmp_path / "events.json"
    predictions = tmp_path / "predictions"
    predictions.mkdir()
    monkeypatch.setattr(collector, "MODULE_A_EVENTS", events)
    monkeypatch.setattr(collector, "MODULE_B_PREDICTIONS_DIR", predictions)
    return events, predictions


def write(events_path, predictions_dir, events, predictions=()):
    events_path.write_text(json.dumps(events), encoding="utf-8")
    for p in predictions:
        (predictions_dir / "{}.json".format(p["event_id"])).write_text(json.dumps(p), encoding="utf-8")


def prediction(event_id, replicas=12):
    return {
        "event_id": event_id,
        "predicted_peak_replicas": replicas,
        "ramp_start": "2026-05-13T09:30:00+05:30",
        "ramp_peak": "2026-05-13T10:15:00+05:30",
        "ramp_end": "2026-05-13T14:00:00+05:30",
    }


def test_each_event_carries_module_bs_forecast(modules):
    write(*modules, [event("cbse_2026", "2026-05-13T10:00:00+05:30")], [prediction("cbse_2026", 13)])

    rows = collector.read_schedule(now=NOW)

    assert rows[0]["event_id"] == "cbse_2026"
    assert rows[0]["predicted_peak_replicas"] == 13
    assert rows[0]["ramp_start"] == "2026-05-13T09:30:00+05:30"


def test_an_event_module_b_has_not_forecast_shows_no_numbers(modules):
    write(*modules, [event("kerala_2026", "2026-06-20T17:00:00+05:30")])

    rows = collector.read_schedule(now=NOW)

    assert rows[0]["predicted_peak_replicas"] is None


def test_events_are_marked_past_or_upcoming_relative_to_now(modules):
    write(*modules, [
        event("old", "2026-05-13T10:00:00+05:30"),
        event("future", "2027-05-13T10:00:00+05:30"),
    ])

    status = {r["event_id"]: r["status"] for r in collector.read_schedule(now=NOW)}

    assert status == {"old": "past", "future": "upcoming"}


def test_the_schedule_is_in_date_order(modules):
    write(*modules, [
        event("august", "2026-08-08T18:00:00+05:30"),
        event("may", "2026-05-13T10:00:00+05:30"),
    ])

    assert [r["event_id"] for r in collector.read_schedule(now=NOW)] == ["may", "august"]


def test_the_event_the_demo_is_replaying_is_flagged(modules):
    write(*modules, [event("cbse_2026", "2026-05-13T10:00:00+05:30"), event("ssc_2026", "2026-08-08T18:00:00+05:30")])

    rows = {r["event_id"]: r for r in collector.read_schedule(now=NOW, demo_event_id="cbse_2026")}

    assert rows["cbse_2026"]["demo"] is True
    assert rows["ssc_2026"]["demo"] is False


def test_no_dataset_means_an_empty_schedule_not_an_error(modules):
    assert collector.read_schedule(now=NOW) == []


def test_the_live_snapshot_includes_the_schedule_with_the_demo_event_flagged(modules, monkeypatch):
    write(*modules, [event("cbse_2026", "2026-05-13T10:00:00+05:30")])
    # Keep the snapshot off Docker and the network -- only the join is under test.
    monkeypatch.setattr(collector, "read_docker_state", lambda: {
        "available": False, "error": "test", "replicas": [], "nginx_running": False})
    monkeypatch.setattr(collector, "read_prediction", lambda: {
        "exists": True, "event_id": "cbse_2026", "kind": "demo (time-shifted)"})

    snapshot = collector.collect(probe_enabled=False)

    assert snapshot["schedule"][0]["event_id"] == "cbse_2026"
    assert snapshot["schedule"][0]["demo"] is True
