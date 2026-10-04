"""Module B: estimate an event's peak traffic and turn it into a Prediction.

Uses proxy signals (registered candidates, comparable past events, the
search-interest curve) instead of the portal's own traffic history, which an
idle-most-of-the-year portal does not have.

Usage:
    python estimate.py [events.json]
"""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

# Project-wide conversion basis.
REQ_PER_MIN_PER_REPLICA = 4000

# Share of registered candidates hitting the portal in the busiest minute.
# Calibrated to the documented example (1,650,000 candidates -> 12 replicas):
# 12 * 4000 / 1,650,000 = 0.0291, rounded to 0.029.
PEAK_CONCURRENCY_RATE = 0.029

# Weight of cohort growth against the comparable prior events.
COMPARABLE_WEIGHT = 0.15


def comparable_growth_factor(candidates, prior_candidates):
    """Multiplier from cohort growth against comparable prior events.

    1.0 when there is no history. Never below 1.0: a shrinking cohort removes
    the nudge but does not cut the base estimate, which the registered count
    already measures directly.

    Args:
        candidates: Registered candidates for this event.
        prior_candidates: Registered candidates for each prior event.

    Returns:
        A factor >= 1.0.
    """
    if not prior_candidates:
        return 1.0

    prior_mean = sum(prior_candidates) / len(prior_candidates)
    if prior_mean <= 0:
        return 1.0

    growth = candidates / prior_mean
    return 1.0 + COMPARABLE_WEIGHT * max(0.0, growth - 1.0)


def estimate_peak_replicas(candidates, prior_candidates):
    """Replicas needed at the event's peak.

    Args:
        candidates: Registered candidates for this event.
        prior_candidates: Registered candidates for each prior event.

    Returns:
        Replica count, rounded up.
    """
    effective_candidates = candidates * comparable_growth_factor(
        candidates, prior_candidates
    )
    peak_req_per_min = effective_candidates * PEAK_CONCURRENCY_RATE

    # Round up: rounding down is exactly the under-provisioning to avoid.
    return math.ceil(peak_req_per_min / REQ_PER_MIN_PER_REPLICA)


# Search interest (0-100) at or above which the portal counts as under event load.
RAMP_INTEREST_THRESHOLD = 10


def ramp_window(event_date, curve):
    """Derive the ramp start, peak and end instants from the interest curve.

    Args:
        event_date: Publication time (timezone-aware).
        curve: (offset_minutes, interest) points relative to event_date,
            sorted by offset.

    Returns:
        Dict with ramp_start, ramp_peak, ramp_end datetimes in the event's
        own offset.

    Raises:
        ValueError: If the curve never reaches the threshold.
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


DEFAULT_CURVE = Path(__file__).resolve().parent / "search_interest_sample.csv"


def load_search_curve(path=None):
    """Read a search-interest CSV into sorted (offset_minutes, interest) points.

    Skips '#' comment lines and the header row. Sorting matters: ramp_window()
    reads the first and last points above the threshold.

    Args:
        path: CSV file. Defaults to the shipped sample curve.

    Returns:
        A list of (int, float) tuples sorted by offset.
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
    """Turn an Event into a Prediction (frozen schema).

    Args:
        event: The Event to predict for.
        prior_events: Its comparable past Events; may be empty.
        curve: Interest curve. Defaults to the shipped sample.

    Returns:
        A Prediction dict with ISO 8601 timestamps.
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


# Standalone sample Events, so the module runs without Module A.
DEFAULT_SAMPLE_EVENTS = Path(__file__).resolve().parent / "sample_events.json"

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "predictions"


def load_events(path=None):
    """Read Events from a JSON file.

    Args:
        path: Module A's dataset or another Event file. Defaults to the samples.

    Returns:
        The list of Events.
    """
    return json.loads(Path(path or DEFAULT_SAMPLE_EVENTS).read_text(encoding="utf-8"))


def predict_all(events, curve=None):
    """Predict every event, resolving priors within the same set.

    Args:
        events: Events to predict; priors outside the set are ignored.
        curve: Interest curve. Defaults to the shipped sample.

    Returns:
        One Prediction per event, in input order.
    """
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
    """Write a Prediction to <output_dir>/<event_id>.json.

    Args:
        prediction: The Prediction to write.
        output_dir: Target folder. Defaults to predictions/.

    Returns:
        Path of the written file.
    """
    directory = Path(output_dir or DEFAULT_OUTPUT_DIR)
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "{}.json".format(prediction["event_id"])
    with path.open("w", encoding="utf-8") as handle:
        json.dump(prediction, handle, indent=2)
        handle.write("\n")
    return path


def summarize(predictions):
    """Format one line per Prediction for the CLI.

    Args:
        predictions: Predictions to describe.

    Returns:
        A list of display lines.
    """
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
