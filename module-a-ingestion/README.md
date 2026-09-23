# CASPER — Module A

**Event Dataset & Ingestion**

Owns the offline civic-event dataset and the loader that reads it. This is the
front of the pipeline: everything downstream starts from an Event produced
here.

```
[Event Calendar Data] → INGESTION (A) → [Event + Metadata] → ESTIMATION (B) → ...
```

---

## ⚠ The dataset is synthetic sample data

`events.json` contains **representative sample figures, not official published
statistics.** The magnitudes are in a plausible range for Indian civic events,
but no number in this file should be quoted in the report, the presentation, or
anywhere else as a real registered-candidate count.

This is deliberate and sufficient: the demo shows that CASPER *provisions from
event metadata rather than traffic history*, and that argument does not depend
on the exact candidate counts being real. If the team later wants real figures,
replace the values and cite the source next to each one — no code changes are
needed.

---

## Run it

```powershell
cd D:\Projects\CASPER\module-a-ingestion
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe loader.py
```

```
Module A -- 6 event(s) from events.json

  cbse_class12_2025                   1,600,000 candidates  exam_result          no history
  cbse_class12_2026                   1,650,000 candidates  exam_result          cbse_class12_2025
  kerala_plustwo_admission_2025         420,000 candidates  admission_deadline   no history
  kerala_plustwo_admission_2026         445,000 candidates  admission_deadline   kerala_plustwo_admission_2025
  ssc_cgl_result_2025                 2,500,000 candidates  recruitment_result   no history
  ssc_cgl_result_2026                 2,650,000 candidates  recruitment_result   ssc_cgl_result_2025
```

No Docker, no network, no services — just Python and a JSON file.

---

## The dataset

Six events: three "current" events that Module B predicts for, each paired with
one prior-year event that gives it history to compare against.

| event_id | type | candidates | prior |
|---|---|---|---|
| `cbse_class12_2025` | exam_result | 1,600,000 | — |
| `cbse_class12_2026` | exam_result | 1,650,000 | `cbse_class12_2025` |
| `kerala_plustwo_admission_2025` | admission_deadline | 420,000 | — |
| `kerala_plustwo_admission_2026` | admission_deadline | 445,000 | `kerala_plustwo_admission_2025` |
| `ssc_cgl_result_2025` | recruitment_result | 2,500,000 | — |
| `ssc_cgl_result_2026` | recruitment_result | 2,650,000 | `ssc_cgl_result_2025` |

The three prior-year events carry no history of their own. That is not an
oversight — an event with `prior_similar_event_ids: []` is the **zero-history
case CASPER exists to handle**, and Module B must still produce a prediction
for it from candidate count alone.

---

## The Event schema (frozen contract)

Do not change field names or types without whole-team agreement.

```json
{
  "event_id": "cbse_class12_2026",
  "board": "CBSE",
  "event_type": "exam_result",
  "date": "2026-05-13T10:00:00+05:30",
  "registered_candidates": 1650000,
  "prior_similar_event_ids": ["cbse_class12_2025"]
}
```

The loader enforces this on every read and refuses to return a dataset that
violates it:

| Rule | Why |
|---|---|
| All six fields present | Module B indexes them directly |
| `registered_candidates` is a positive integer | It is the dominant term in B's estimate; `0` or `"1.6M"` would silently corrupt the prediction |
| `date` parses as ISO 8601 **with a timezone offset** | Module C schedules real scale-up actions against this instant — a naive timestamp is ambiguous about when capacity should appear |
| `event_id` values are unique | `get_event` returns the first match, so duplicates would silently shadow each other |
| Every `prior_similar_event_ids` entry exists in the dataset | A dangling reference would break B's comparable-peak signal at estimation time, not load time |

Unknown extra fields are allowed — the schema is a minimum contract, which is
how the `_comment` marker in `events.json` can sit alongside the real fields.

---

## API — what Module B consumes

```python
import loader

events = loader.load_events()                      # the shipped dataset
events = loader.load_events("some/other.json")     # or any dataset file

event  = loader.get_event(events, "cbse_class12_2026")
priors = loader.get_prior_events(events, event)    # [] for a first-time event
```

| Raises | When |
|---|---|
| `loader.InvalidEventError` | The dataset violates the Event schema |
| `loader.EventNotFoundError` | A requested (or referenced) `event_id` is not in the dataset |

---

## Tests

Built test-first. 17 tests, no mocks — every test runs the real loader against a
real JSON file written to a temp directory.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

Coverage: each validation rule above has a test that fails without it, plus
tests asserting the *shipped* dataset loads, resolves every prior reference,
covers all three event types, and gives each current event exactly one prior.

---

## Files

```
module-a-ingestion/
├── events.json       The dataset (SYNTHETIC — see warning above)
├── loader.py         Loader + validation + CLI
├── tests/
│   ├── conftest.py   Puts the module root on sys.path
│   └── test_loader.py
├── requirements.txt  pytest (dev only — the loader is stdlib-only)
└── README.md
```
