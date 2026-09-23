"""Module B -- traffic-magnitude estimation.

Turns an Event (Module A's output) into a Prediction (Module C's input) using
proxy signals instead of the portal's own traffic history, which is the whole
point: a portal that is idle 364 days a year has no history to learn from.
"""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

# --- Calibration -----------------------------------------------------------
#
# Documented conversion basis, fixed across the project: one portal replica
# serves roughly 4000 requests per minute.
REQ_PER_MIN_PER_REPLICA = 4000

# Share of registered candidates expected to hit the portal in the single
# busiest minute.
#
# This is the one calibrated constant in the model, and it is pinned to the
# worked example frozen into every schema sample in the project docs:
# 1,650,000 candidates -> 12 replicas.
#
#     12 replicas * 4000 req/min = 48,000 req/min at peak
#     48,000 / 1,650,000         = 0.0291 req per candidate per minute
#
# Rounded to 0.029, i.e. ~2.9% of registered candidates refreshing within the
# same minute. Plausible for a result announcement, where the publication
# time is known in advance and candidates are already waiting.
PEAK_CONCURRENCY_RATE = 0.029

# Weight on the comparable-prior-event signal.
#
# The registered-candidate count is already a direct measure of this event's
# scale, so it carries most of the estimate. A comparable prior event adds one
# thing the count alone cannot show: the trend. A cohort that has grown since
# last year tends to bring proportionally heavier same-minute demand (more
# first-time candidates, wider phone access), so growth nudges the estimate up.
#
# The adjustment is deliberately one-directional -- see below.
COMPARABLE_WEIGHT = 0.15


def comparable_growth_factor(candidates, prior_candidates):
    """Multiplier (>= 1.0) from how this event compares with its history.

    Returns 1.0 -- no adjustment -- for a first-time event with no priors.
    That is not a gap in the model: a zero-history event is precisely the case
    CASPER is built for, and the registered-candidate count carries it alone.

    The factor never drops below 1.0. A prior larger than the current event is
    not evidence that less capacity is needed; the registered count already
    measures this event's scale directly, so a shrinking cohort simply removes
    the upward nudge rather than cutting into the base estimate.
    """
    if not prior_candidates:
        return 1.0

    prior_mean = sum(prior_candidates) / len(prior_candidates)
    if prior_mean <= 0:
        return 1.0

    growth = candidates / prior_mean
    return 1.0 + COMPARABLE_WEIGHT * max(0.0, growth - 1.0)


def estimate_peak_replicas(candidates, prior_candidates):
    """Predict the replica count needed at peak for an event."""
    effective_candidates = candidates * comparable_growth_factor(
        candidates, prior_candidates
    )
    peak_req_per_min = effective_candidates * PEAK_CONCURRENCY_RATE

    # Always round up. A fractional replica cannot be run, and rounding down
    # is the under-provisioning that makes portals fall over on result day.
    return math.ceil(peak_req_per_min / REQ_PER_MIN_PER_REPLICA)


# Interest level (0-100 on the search-interest curve) at which the portal is
# considered to be under event traffic. Below this, demand is background noise
# and the extra replicas are wasted money.
RAMP_INTEREST_THRESHOLD = 10


def ramp_window(event_date, curve):
    """Derive the scale-up / peak / scale-down instants from the curve.

    The curve is the synthetic search-interest signal: (offset_minutes,
    interest) points relative to the event's publication time, shaped like a
    Google Trends result-day spike. It supplies the *timing* of the event --
    the candidate count supplies its magnitude.

    All three instants keep the event's own timezone offset, because Module C
    schedules real scale actions against them.
    """
    above = [point for point in curve if point[1] >= RAMP_INTEREST_THRESHOLD]
    if not above:
        raise ValueError(
            "search-interest curve never reaches the ramp threshold of {}; "
            "there is no window to schedule against".format(RAMP_INTEREST_THRESHOLD)
        )

    start_offset = above[0][0]
    end_offset = above[-1][0]
    peak_offset = max(curve, key=lambda point: point[1])[0]

    return {
        "ramp_start": event_date + timedelta(minutes=start_offset),
        "ramp_peak": event_date + timedelta(minutes=peak_offset),
        "ramp_end": event_date + timedelta(minutes=end_offset),
    }


# The synthetic search-interest curve this module ships.
DEFAULT_CURVE = Path(__file__).resolve().parent / "search_interest_sample.csv"


def load_search_curve(path=None):
    """Read a search-interest curve CSV into (offset_minutes, interest) points.

    Lines starting with '#' are comments and the first data row is the header.
    Points are returned sorted by offset, since ramp_window() reads the first
    and last points above the threshold and an out-of-order file would
    silently produce a reversed window.
    """
    points = []
    for line in Path(path or DEFAULT_CURVE).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("offset_minutes"):
            continue
        offset, interest = line.split(",")
        points.append((int(offset), float(interest)))

    return sorted(points, key=lambda point: point[0])


def predict(event, prior_events, curve=None):
    """Turn an Event into a Prediction.

    This is Module B's whole job and the contract Module C consumes:

        Event (Module A)  ->  predict()  ->  Prediction (Module C)

    `prior_events` are the comparable past events Module A resolved from
    `prior_similar_event_ids`. An empty list is valid and meaningful -- it is
    the zero-history event the project is built around.
    """
    event_date = datetime.fromisoformat(event["date"])
    window = ramp_window(event_date, curve or load_search_curve())

    replicas = estimate_peak_replicas(
        candidates=event["registered_candidates"],
        prior_candidates=[prior["registered_candidates"] for prior in prior_events],
    )

    return {
        "event_id": event["event_id"],
        "predicted_peak_replicas": replicas,
        "ramp_start": window["ramp_start"].isoformat(),
        "ramp_peak": window["ramp_peak"].isoformat(),
        "ramp_end": window["ramp_end"].isoformat(),
    }


# Hand-authored sample Events, so this module is testable and demoable on its
# own before Module A's dataset is wired in. Same frozen Event schema.
DEFAULT_SAMPLE_EVENTS = Path(__file__).resolve().parent / "sample_events.json"

# Where generated Predictions are written, one JSON file per event.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "predictions"


def load_events(path=None):
    """Read Events from a JSON file (Module A's dataset, or the samples)."""
    return json.loads(Path(path or DEFAULT_SAMPLE_EVENTS).read_text(encoding="utf-8"))


def predict_all(events, curve=None):
    """Produce a Prediction for every event, resolving priors within the set."""
    by_id = {event["event_id"]: event for event in events}

    predictions = []
    for event in events:
        priors = [
            by_id[prior_id]
            for prior_id in event["prior_similar_event_ids"]
            if prior_id in by_id
        ]
        predictions.append(predict(event, prior_events=priors, curve=curve))
    return predictions


def write_prediction(prediction, output_dir=None):
    """Write one Prediction to <output_dir>/<event_id>.json and return the path."""
    directory = Path(output_dir or DEFAULT_OUTPUT_DIR)
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "{}.json".format(prediction["event_id"])
    with path.open("w", encoding="utf-8") as handle:
        json.dump(prediction, handle, indent=2)
        handle.write("\n")
    return path


def summarize(predictions):
    """One human-readable line per Prediction, for the CLI output."""
    lines = []
    for prediction in predictions:
        start = datetime.fromisoformat(prediction["ramp_start"])
        end = datetime.fromisoformat(prediction["ramp_end"])
        lines.append(
            "{:<32} {:>3} replicas at peak   ramp {} -> {}".format(
                prediction["event_id"],
                prediction["predicted_peak_replicas"],
                start.strftime("%Y-%m-%d %H:%M"),
                end.strftime("%H:%M"),
            )
        )
    return lines


if __name__ == "__main__":
    # Deliverable: produce a Prediction for every event and write them out.
    #     python estimate.py                      (uses the sample Events)
    #     python estimate.py ../module-a-ingestion/events.json
    import sys

    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_EVENTS
    loaded = load_events(source)
    results = predict_all(loaded)

    print("Module B -- {} prediction(s) from {}".format(len(results), source.name))
    print()
    for summary_line in summarize(results):
        print("  " + summary_line)
    print()
    for result in results:
        print("  wrote {}".format(write_prediction(result)))
    print()
    print("Calibration: {:.3f} req/candidate/min, {} req/min per replica.".format(
        PEAK_CONCURRENCY_RATE, REQ_PER_MIN_PER_REPLICA
    ))
