"""Module A: load and validate the civic event dataset (frozen Event schema).

Usage:
    python loader.py
"""

import json
from datetime import datetime
from pathlib import Path

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
    """An event does not match the Event schema."""


class EventNotFoundError(KeyError):
    """A requested event_id is not in the dataset."""


def load_events(path=None):
    """Read and validate an event dataset.

    Args:
        path: JSON file to read. Defaults to the shipped events.json.

    Returns:
        The list of Event dicts.

    Raises:
        InvalidEventError: If an event breaks the schema or an id repeats.
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
    """Find one event by id.

    Args:
        events: Loaded events.
        event_id: Id to look up.

    Returns:
        The matching Event.

    Raises:
        EventNotFoundError: If no event has that id.
    """
    for event in events:
        if event["event_id"] == event_id:
            return event
    raise EventNotFoundError(
        "no event with event_id {!r} in the dataset".format(event_id)
    )


def get_prior_events(events, event):
    """Resolve an event's prior_similar_event_ids to the events themselves.

    An empty result is valid: a first-time event with no history.

    Args:
        events: Loaded events.
        event: The event whose priors to resolve.

    Returns:
        The prior Events, in reference order.

    Raises:
        EventNotFoundError: If a referenced prior is missing.
    """
    return [get_event(events, prior_id) for prior_id in event["prior_similar_event_ids"]]


def _validate(event):
    """Raise InvalidEventError unless `event` satisfies the Event schema."""
    event_id = event.get("event_id", "<no event_id>")

    for field in REQUIRED_FIELDS:
        if field not in event:
            raise InvalidEventError(
                "event {!r} is missing required field {!r}".format(event_id, field)
            )

    _validate_date(event_id, event["date"])

    candidates = event["registered_candidates"]
    # bool is an int subclass; reject True explicitly.
    if isinstance(candidates, bool) or not isinstance(candidates, int) or candidates <= 0:
        raise InvalidEventError(
            "event {!r} has registered_candidates {!r}; expected a positive integer".format(
                event_id, candidates
            )
        )


def _validate_date(event_id, raw_date):
    """Require ISO 8601 with a timezone offset.

    Module C schedules against these instants, so a naive time is ambiguous.

    Raises:
        InvalidEventError: If the date is unparseable or has no offset.
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
    """Format one line per event for the CLI.

    Args:
        events: Loaded events.

    Returns:
        A list of display lines.
    """
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
    loaded = load_events()
    print("Module A -- {} event(s) from {}".format(len(loaded), DEFAULT_DATASET.name))
    print()
    for line in summarize(loaded):
        print("  " + line)
    print()
    print("SYNTHETIC SAMPLE DATA -- see README.md before quoting these numbers.")
