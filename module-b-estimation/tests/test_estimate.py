"""Tests for Module B's traffic-magnitude estimation model."""

import json

import pytest

import estimate


def test_the_documented_example_yields_the_documented_replica_count():
    # Every schema sample in the project docs pairs 1,650,000 registered
    # candidates with predicted_peak_replicas: 12. The model is calibrated to
    # reproduce that figure, so this test pins the calibration.
    replicas = estimate.estimate_peak_replicas(candidates=1_650_000, prior_candidates=[])

    assert replicas == 12


def test_a_fractional_replica_requirement_always_rounds_up():
    # 100,000 * 0.029 = 2900 req/min = 0.725 replicas. Rounding down to 0 --
    # or even to 1 from 1.9 -- is exactly the under-provisioning failure the
    # project exists to prevent.
    assert estimate.estimate_peak_replicas(candidates=100_000, prior_candidates=[]) == 1


def test_an_event_growing_against_its_prior_is_provisioned_higher():
    growing = estimate.estimate_peak_replicas(
        candidates=1_000_000, prior_candidates=[500_000]
    )
    flat = estimate.estimate_peak_replicas(
        candidates=1_000_000, prior_candidates=[1_000_000]
    )

    assert growing > flat


def test_a_prior_larger_than_the_current_event_does_not_lower_the_estimate():
    # A shrinking cohort is not evidence that less capacity is needed -- the
    # registered count is already the direct measure. The comparable signal
    # may raise the estimate, never cut it.
    shrinking = estimate.estimate_peak_replicas(
        candidates=1_000_000, prior_candidates=[2_000_000]
    )
    no_history = estimate.estimate_peak_replicas(
        candidates=1_000_000, prior_candidates=[]
    )

    assert shrinking == no_history


# --- ramp window from the search-interest curve ----------------------------

from datetime import datetime  # noqa: E402  (grouped with the tests that use it)


def test_ramp_window_starts_when_interest_first_crosses_the_threshold():
    event_date = datetime.fromisoformat("2026-05-13T10:00:00+05:30")
    curve = [(-60, 2), (-30, 10), (0, 80), (15, 100), (240, 10), (300, 4)]

    window = estimate.ramp_window(event_date, curve)

    assert window["ramp_start"] == datetime.fromisoformat("2026-05-13T09:30:00+05:30")


def test_ramp_window_peaks_at_the_curves_highest_interest():
    event_date = datetime.fromisoformat("2026-05-13T10:00:00+05:30")
    curve = [(-60, 2), (-30, 10), (0, 80), (15, 100), (240, 10), (300, 4)]

    window = estimate.ramp_window(event_date, curve)

    assert window["ramp_peak"] == datetime.fromisoformat("2026-05-13T10:15:00+05:30")


def test_ramp_window_ends_when_interest_falls_back_below_the_threshold():
    event_date = datetime.fromisoformat("2026-05-13T10:00:00+05:30")
    curve = [(-60, 2), (-30, 10), (0, 80), (15, 100), (240, 10), (300, 4)]

    window = estimate.ramp_window(event_date, curve)

    assert window["ramp_end"] == datetime.fromisoformat("2026-05-13T14:00:00+05:30")


def test_ramp_window_preserves_the_events_timezone_offset():
    # Module C schedules against these instants; drifting to UTC would move
    # every scale-up by five and a half hours.
    event_date = datetime.fromisoformat("2026-05-13T10:00:00+05:30")
    curve = [(-30, 10), (15, 100), (240, 10)]

    window = estimate.ramp_window(event_date, curve)

    assert window["ramp_start"].utcoffset() == event_date.utcoffset()


# --- the shipped search-interest curve --------------------------------------


def test_the_shipped_curve_reproduces_the_documented_ramp_offsets():
    # The documented Prediction pairs a 10:00 event with ramp_start 09:30,
    # ramp_peak 10:15 and ramp_end 14:00. The shipped curve is shaped to
    # produce exactly those offsets.
    curve = estimate.load_search_curve()
    event_date = datetime.fromisoformat("2026-05-13T10:00:00+05:30")

    window = estimate.ramp_window(event_date, curve)

    assert window["ramp_start"] == datetime.fromisoformat("2026-05-13T09:30:00+05:30")
    assert window["ramp_peak"] == datetime.fromisoformat("2026-05-13T10:15:00+05:30")
    assert window["ramp_end"] == datetime.fromisoformat("2026-05-13T14:00:00+05:30")


def test_the_shipped_curve_is_ordered_by_offset():
    # ramp_start/ramp_end read the first and last points above the threshold,
    # so an out-of-order curve would silently produce a reversed window.
    curve = estimate.load_search_curve()

    offsets = [offset for offset, _ in curve]
    assert offsets == sorted(offsets)


# --- predict(): Event in, Prediction out ------------------------------------


DOCUMENTED_EVENT = {
    "event_id": "cbse_class12_2025",
    "board": "CBSE",
    "event_type": "exam_result",
    "date": "2025-05-13T10:00:00+05:30",
    "registered_candidates": 1650000,
    "prior_similar_event_ids": ["cbse_class12_2024"],
}


def test_predict_reproduces_the_documented_prediction_exactly():
    # The end-to-end anchor: the Event printed in the project docs must yield
    # the Prediction printed in the project docs, field for field. Priors are
    # passed empty because the docs give no candidate count for the 2024
    # event, so only the signals the docs actually supply are used.
    prediction = estimate.predict(DOCUMENTED_EVENT, prior_events=[])

    assert prediction == {
        "event_id": "cbse_class12_2025",
        "predicted_peak_replicas": 12,
        "ramp_start": "2025-05-13T09:30:00+05:30",
        "ramp_peak": "2025-05-13T10:15:00+05:30",
        "ramp_end": "2025-05-13T14:00:00+05:30",
    }


def test_predict_uses_the_candidate_counts_of_the_prior_events_given_to_it():
    priors = [dict(DOCUMENTED_EVENT, event_id="cbse_class12_2024", registered_candidates=800000)]

    with_history = estimate.predict(DOCUMENTED_EVENT, prior_events=priors)
    without_history = estimate.predict(DOCUMENTED_EVENT, prior_events=[])

    # Cohort roughly doubled, so the growth signal must raise the estimate.
    assert with_history["predicted_peak_replicas"] > without_history["predicted_peak_replicas"]


def test_predict_emits_timestamps_in_ramp_order():
    prediction = estimate.predict(DOCUMENTED_EVENT, prior_events=[])

    start = datetime.fromisoformat(prediction["ramp_start"])
    peak = datetime.fromisoformat(prediction["ramp_peak"])
    end = datetime.fromisoformat(prediction["ramp_end"])

    assert start < peak < end


def test_predict_emits_exactly_the_frozen_prediction_schema_fields():
    # Module C reads these keys directly; an extra or renamed key is a
    # contract break, not a cosmetic difference.
    prediction = estimate.predict(DOCUMENTED_EVENT, prior_events=[])

    assert set(prediction) == {
        "event_id",
        "predicted_peak_replicas",
        "ramp_start",
        "ramp_peak",
        "ramp_end",
    }


# --- standalone operation and output ----------------------------------------


def test_the_shipped_sample_events_produce_valid_predictions():
    # Module B ships its own sample Event file so it is testable and
    # demoable before Module A's dataset is wired in.
    events = estimate.load_events(estimate.DEFAULT_SAMPLE_EVENTS)

    predictions = estimate.predict_all(events)

    assert len(predictions) == len(events)
    for prediction in predictions:
        assert prediction["predicted_peak_replicas"] >= 1


def test_predict_all_resolves_priors_from_within_the_given_events():
    events = [
        {
            "event_id": "prior_2025",
            "board": "X",
            "event_type": "exam_result",
            "date": "2025-05-13T10:00:00+05:30",
            "registered_candidates": 500000,
            "prior_similar_event_ids": [],
        },
        {
            "event_id": "current_2026",
            "board": "X",
            "event_type": "exam_result",
            "date": "2026-05-13T10:00:00+05:30",
            "registered_candidates": 1000000,
            "prior_similar_event_ids": ["prior_2025"],
        },
    ]

    predictions = {p["event_id"]: p for p in estimate.predict_all(events)}

    # current_2026 doubled against its prior, so its estimate must exceed the
    # estimate it would get from its candidate count alone.
    alone = estimate.estimate_peak_replicas(candidates=1000000, prior_candidates=[])
    assert predictions["current_2026"]["predicted_peak_replicas"] > alone


def test_write_prediction_saves_one_json_file_named_for_the_event(tmp_path):
    prediction = estimate.predict(DOCUMENTED_EVENT, prior_events=[])

    written = estimate.write_prediction(prediction, tmp_path)

    assert written.name == "cbse_class12_2025.json"
    assert json.loads(written.read_text(encoding="utf-8")) == prediction


def test_ramp_window_rejects_a_curve_that_never_reaches_the_threshold():
    # A flat curve gives no window to schedule against. Failing here is far
    # better than handing Module C a nonsense ramp.
    event_date = datetime.fromisoformat("2026-05-13T10:00:00+05:30")
    flat_curve = [(-30, 1), (0, 2), (30, 1)]

    with pytest.raises(ValueError):
        estimate.ramp_window(event_date, flat_curve)


def test_summarize_reports_replica_count_and_ramp_start_per_prediction():
    prediction = estimate.predict(DOCUMENTED_EVENT, prior_events=[])

    lines = estimate.summarize([prediction])

    assert len(lines) == 1
    assert "cbse_class12_2025" in lines[0]
    assert "12" in lines[0]
    assert "09:30" in lines[0]
