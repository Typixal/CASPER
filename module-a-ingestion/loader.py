"""Module A -- civic event dataset loader."""

import json
from datetime import datetime
from pathlib import Path

# The dataset this module ships. Callers (Module B, the dashboard) can just
# call load_events() and get it, without knowing where the file lives.
DEFAULT_DATASET = Path(__file__).resolve().parent / "events.json"

REQUIRED_FIELDS = (
    "event_id",
    "board",
    "event_type",
    "date",
    "registered_candidates",
    "prior_similar_event_ids",
)


class InvalidEventError(ValueError):
    """Raised when an event does not match the frozen Event schema."""


class EventNotFoundError(KeyError):
    """Raised when a requested event_id is not present in the dataset."""


def load_events(path=None):
    """Read an event dataset, validate it, and return its events.

    With no argument, reads the dataset this module ships.
    """
    events = json.loads(Path(path or DEFAULT_DATASET).read_text(encoding="utf-8"))

    seen = set()
    for event in events:
        _validate(event)
        event_id = event["event_id"]
        if event_id in seen:
            raise InvalidEventError(
                "duplicate event_id {!r} in the dataset; ids must be unique".format(event_id)
            )
        seen.add(event_id)

    return events


def get_event(events, event_id):
    """Return the event with `event_id`, or raise EventNotFoundError."""
    for event in events:
        if event["event_id"] == event_id:
            return event
    raise EventNotFoundError(
        "no event with event_id {!r} in the dataset".format(event_id)
    )


def get_prior_events(events, event):
    """Resolve an event's prior_similar_event_ids into the events themselves.

    This is the "comparable past events" proxy signal Module B estimates
    from. An empty list is a legitimate, meaningful answer -- it means a
    first-time event with no history, which is exactly the case CASPER
    exists to handle.
    """
    return [get_event(events, prior_id) for prior_id in event["prior_similar_event_ids"]]


def _validate(event):
    event_id = event.get("event_id", "<no event_id>")

    for field in REQUIRED_FIELDS:
        if field not in event:
            raise InvalidEventError(
                "event {!r} is missing required field {!r}".format(event_id, field)
            )

    _validate_date(event_id, event["date"])

    candidates = event["registered_candidates"]
    # bool is a subclass of int in Python, so reject it explicitly rather than
    # letting True sail through as the number 1.
    if isinstance(candidates, bool) or not isinstance(candidates, int) or candidates <= 0:
        raise InvalidEventError(
            "event {!r} has registered_candidates {!r}; expected a positive integer".format(
                event_id, candidates
            )
        )


def _validate_date(event_id, raw_date):
    """The schema requires ISO 8601 *with* a timezone offset.

    Module C schedules real scale-up actions against these instants, so a
    naive timestamp is not merely untidy -- it is ambiguous about when
    capacity should actually appear.
    """
    try:
        parsed = datetime.fromisoformat(raw_date)
    except (TypeError, ValueError):
        raise InvalidEventError(
            "event {!r} has date {!r}; expected ISO 8601, e.g. "
            "'2026-05-13T10:00:00+05:30'".format(event_id, raw_date)
        ) from None

    if parsed.tzinfo is None:
        raise InvalidEventError(
            "event {!r} has date {!r} with no timezone offset; "
            "the Event schema requires one (IST is '+05:30')".format(event_id, raw_date)
        )


def summarize(events):
    """One human-readable line per event, for the loader's CLI output."""
    lines = []
    for event in events:
        priors = event["prior_similar_event_ids"]
        history = ", ".join(priors) if priors else "no history"
        lines.append(
            "{:<32} {:>12} candidates  {:<20} {}".format(
                event["event_id"],
                "{:,}".format(event["registered_candidates"]),
                event["event_type"],
                history,
            )
        )
    return lines


if __name__ == "__main__":
    # Deliverable: run the loader directly to see what the dataset holds.
    #     python loader.py
    loaded = load_events()
    print("Module A -- {} event(s) from {}".format(len(loaded), DEFAULT_DATASET.name))
    print()
    for line in summarize(loaded):
        print("  " + line)
    print()
    print("SYNTHETIC SAMPLE DATA -- see README.md before quoting these numbers.")
