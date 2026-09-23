"""Tests for Module A's event loader."""

import json

import pytest

import loader


def write_dataset(tmp_path, events):
    """Write an events.json containing `events` and return its path."""
    path = tmp_path / "events.json"
    path.write_text(json.dumps(events), encoding="utf-8")
    return path


def valid_event(**overrides):
    """A schema-valid Event, with any field overridable per test."""
    event = {
        "event_id": "cbse_class12_2026",
        "board": "CBSE",
        "event_type": "exam_result",
        "date": "2026-05-13T10:00:00+05:30",
        "registered_candidates": 1650000,
        "prior_similar_event_ids": [],
    }
    event.update(overrides)
    return event


def test_load_events_returns_every_event_in_the_dataset(tmp_path):
    path = write_dataset(
        tmp_path,
        [valid_event(event_id="cbse_class12_2026"), valid_event(event_id="kerala_sslc_2026")],
    )

    events = loader.load_events(path)

    assert [e["event_id"] for e in events] == ["cbse_class12_2026", "kerala_sslc_2026"]


def test_load_events_rejects_an_event_missing_a_required_field(tmp_path):
    incomplete = valid_event()
    del incomplete["registered_candidates"]
    path = write_dataset(tmp_path, [incomplete])

    with pytest.raises(loader.InvalidEventError) as excinfo:
        loader.load_events(path)

    assert "registered_candidates" in str(excinfo.value)


def test_load_events_rejects_a_non_positive_candidate_count(tmp_path):
    path = write_dataset(tmp_path, [valid_event(registered_candidates=0)])

    with pytest.raises(loader.InvalidEventError) as excinfo:
        loader.load_events(path)

    assert "registered_candidates" in str(excinfo.value)


def test_load_events_rejects_a_date_without_a_timezone_offset(tmp_path):
    # The frozen Event schema requires ISO 8601 *with* an offset -- Module C
    # schedules against these instants, so a naive timestamp is ambiguous.
    path = write_dataset(tmp_path, [valid_event(date="2026-05-13T10:00:00")])

    with pytest.raises(loader.InvalidEventError) as excinfo:
        loader.load_events(path)

    assert "timezone" in str(excinfo.value).lower()


def test_load_events_rejects_an_unparseable_date(tmp_path):
    path = write_dataset(tmp_path, [valid_event(date="13-05-2026 10:00")])

    with pytest.raises(loader.InvalidEventError):
        loader.load_events(path)


def test_get_event_returns_the_event_with_that_id(tmp_path):
    path = write_dataset(
        tmp_path,
        [valid_event(event_id="cbse_class12_2025"), valid_event(event_id="kerala_sslc_2026")],
    )
    events = loader.load_events(path)

    found = loader.get_event(events, "kerala_sslc_2026")

    assert found["event_id"] == "kerala_sslc_2026"


def test_get_event_raises_for_an_unknown_id(tmp_path):
    path = write_dataset(tmp_path, [valid_event(event_id="cbse_class12_2026")])
    events = loader.load_events(path)

    with pytest.raises(loader.EventNotFoundError):
        loader.get_event(events, "does_not_exist_2026")


def test_get_prior_events_resolves_ids_to_the_actual_events(tmp_path):
    path = write_dataset(
        tmp_path,
        [
            valid_event(event_id="cbse_class12_2025", registered_candidates=1600000),
            valid_event(
                event_id="cbse_class12_2026",
                prior_similar_event_ids=["cbse_class12_2025"],
            ),
        ],
    )
    events = loader.load_events(path)
    current = loader.get_event(events, "cbse_class12_2026")

    priors = loader.get_prior_events(events, current)

    assert [p["event_id"] for p in priors] == ["cbse_class12_2025"]
    assert priors[0]["registered_candidates"] == 1600000


def test_get_prior_events_returns_empty_when_the_event_has_no_history(tmp_path):
    # This is the zero-history case CASPER exists for: a first-time event.
    path = write_dataset(tmp_path, [valid_event(prior_similar_event_ids=[])])
    events = loader.load_events(path)

    assert loader.get_prior_events(events, events[0]) == []


def test_get_prior_events_raises_when_a_referenced_prior_is_missing(tmp_path):
    path = write_dataset(
        tmp_path,
        [valid_event(event_id="cbse_class12_2026", prior_similar_event_ids=["ghost_2025"])],
    )
    events = loader.load_events(path)

    with pytest.raises(loader.EventNotFoundError):
        loader.get_prior_events(events, events[0])


def test_load_events_rejects_duplicate_event_ids(tmp_path):
    # get_event returns the first match, so duplicates would silently shadow
    # one another rather than failing loudly.
    path = write_dataset(
        tmp_path,
        [valid_event(event_id="cbse_class12_2026"), valid_event(event_id="cbse_class12_2026")],
    )

    with pytest.raises(loader.InvalidEventError) as excinfo:
        loader.load_events(path)

    assert "cbse_class12_2026" in str(excinfo.value)


# --- the dataset Module A actually ships -----------------------------------


def test_the_shipped_dataset_loads_and_validates():
    # load_events() with no argument reads the module's own events.json, so
    # Module B can consume the dataset without knowing where it lives.
    events = loader.load_events()

    assert len(events) == 6


def test_every_prior_reference_in_the_shipped_dataset_resolves():
    events = loader.load_events()

    for event in events:
        # Raises EventNotFoundError if the dataset references a prior that
        # isn't in it -- a dangling reference would break Module B.
        loader.get_prior_events(events, event)


def test_the_shipped_dataset_covers_the_three_event_types():
    events = loader.load_events()

    assert {e["event_type"] for e in events} == {
        "exam_result",
        "admission_deadline",
        "recruitment_result",
    }


def test_the_shipped_dataset_gives_every_current_event_a_prior():
    # Module B's comparable-peak signal needs history to work with, so each
    # of the three current events must reference a prior-year event.
    events = loader.load_events()

    with_priors = [e for e in events if e["prior_similar_event_ids"]]
    assert len(with_priors) == 3


def test_summarize_reports_one_line_per_event_with_its_candidate_count(tmp_path):
    path = write_dataset(
        tmp_path,
        [valid_event(event_id="cbse_class12_2026", registered_candidates=1650000)],
    )
    events = loader.load_events(path)

    lines = loader.summarize(events)

    assert len(lines) == 1
    assert "cbse_class12_2026" in lines[0]
    assert "1,650,000" in lines[0]


def test_summarize_marks_an_event_that_has_no_prior_history(tmp_path):
    path = write_dataset(tmp_path, [valid_event(prior_similar_event_ids=[])])
    events = loader.load_events(path)

    assert "no history" in loader.summarize(events)[0]
