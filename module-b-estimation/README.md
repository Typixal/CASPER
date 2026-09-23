# CASPER — Module B

**Traffic-Magnitude Estimation Model**

The project's primary technical contribution. Turns an Event into a Prediction
using *proxy signals* instead of the portal's own traffic history — which is
the whole point, since a portal idle 364 days a year has no history to learn
from.

```
Event (Module A) → predict() → Prediction (Module C)
```

---

## The formula

```
                      ┌─ registered candidates  (magnitude)
predicted_peak_replicas ─┼─ comparable prior events (trend)
                      └─ search-interest curve  (timing)
```

```python
effective_candidates = candidates × comparable_growth_factor
peak_req_per_min     = effective_candidates × PEAK_CONCURRENCY_RATE
predicted_peak_replicas = ceil(peak_req_per_min / REQ_PER_MIN_PER_REPLICA)
```

### The one calibrated constant

`PEAK_CONCURRENCY_RATE = 0.029` — the share of registered candidates expected
to hit the portal in the single busiest minute.

It is not a guess. It is **pinned to the worked example frozen into every
schema sample in the project docs**: 1,650,000 candidates → 12 replicas.

```
12 replicas × 4000 req/min   = 48,000 req/min at peak
48,000 / 1,650,000           = 0.0291 req per candidate per minute
                             → 0.029  (≈2.9% of candidates in the same minute)
```

Plausible for a result announcement: the publication time is known in advance,
so candidates are already waiting and refresh together rather than arriving
spread out.

`REQ_PER_MIN_PER_REPLICA = 4000` is the conversion basis documented across the
whole project, not something this module chose.

### The comparable-prior term

```python
growth = candidates / mean(prior_candidates)
comparable_growth_factor = 1 + 0.15 × max(0, growth − 1)
```

The registered count already measures this event's scale directly, so it
carries most of the estimate. A comparable prior event adds the one thing the
count cannot show — the **trend**. A cohort that has grown since last year
tends to bring proportionally heavier same-minute demand, so growth nudges the
estimate up by `COMPARABLE_WEIGHT = 0.15` of the growth rate.

Two deliberate properties:

- **It never lowers the estimate.** A prior *larger* than the current event is
  not evidence that less capacity is needed — the registered count already
  measures this event. A shrinking cohort simply removes the upward nudge.
- **No priors returns exactly 1.0.** A first-time event is not a degraded
  case to apologise for; it is the case CASPER is built for, and the candidate
  count carries it alone.

### Sensitivity

How `predicted_peak_replicas` moves with each input, holding the others fixed:

| candidates | priors | growth | factor | req/min | replicas |
|---|---|---|---|---|---|
| 1,650,000 | — | — | 1.000 | 47,850 | **12** ← documented example |
| 1,650,000 | 1,600,000 | 1.031 | 1.005 | 48,074 | 13 |
| 1,700,000 | 1,650,000 | 1.030 | 1.005 | 49,524 | 13 |
| 1,650,000 | 2,000,000 | 0.825 | 1.000 | 47,850 | 12 (prior larger → no cut) |
| 420,000 | — | — | 1.000 | 12,180 | 4 |
| 2,650,000 | 2,500,000 | 1.060 | 1.009 | 77,542 | 20 |
| 100,000 | — | — | 1.000 | 2,900 | 1 (never 0) |

The estimate is dominated by the candidate count, as it should be — the
comparable term moves it by single-digit percent. `ceil` means a growing
event sitting just under a replica boundary (1,650,000 + any growth) tips to
the next replica. That is the intended bias: **under-provisioning is the
failure this project exists to prevent**, so the model rounds toward safety.

---

## The search-interest curve — where the timing comes from

`search_interest_sample.csv` is a **synthetic** Google-Trends-shaped curve,
built once by hand. Nothing is fetched live, at build time or demo time.

```
offset_minutes,interest     # offset is relative to publication time
-30,10                      # ← interest crosses the threshold: ramp_start
  0,80
 15,100                     # ← highest interest: ramp_peak
240,10                      # ← last point above threshold: ramp_end
```

With `RAMP_INTEREST_THRESHOLD = 10`, a 10:00 event yields **ramp_start 09:30,
ramp_peak 10:15, ramp_end 14:00** — exactly the window in the documented
Prediction. The shape encodes what a candidate count cannot: candidates start
refreshing *before* the announced time, interest peaks shortly *after*
publication (late arrivals and retries), then decays over hours.

---

## Run it

```powershell
cd D:\Projects\CASPER\module-b-estimation
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe estimate.py                              # sample Events
.\.venv\Scripts\python.exe estimate.py ..\module-a-ingestion\events.json   # Module A's dataset
```

```
Module B -- 2 prediction(s) from sample_events.json

  cbse_class12_2025                 12 replicas at peak   ramp 2025-05-13 09:30 -> 14:00
  cbse_class12_2026                 13 replicas at peak   ramp 2026-05-13 09:30 -> 14:00

  wrote predictions\cbse_class12_2025.json
  wrote predictions\cbse_class12_2026.json
```

No Docker, no network, no services — Python standard library only. (pandas is
listed in the project's tech stack, but a weighted formula over a handful of
events does not need a dataframe, and every dependency is one more thing to
install before a demo.)

Module B ships `sample_events.json` so it runs standalone before Module A is
wired in — the documented pattern for building modules in parallel against
frozen contracts.

---

## Output — the Prediction schema (frozen contract)

One file per event in `predictions/`, consumed by Module C as-is:

```json
{
  "event_id": "cbse_class12_2025",
  "predicted_peak_replicas": 12,
  "ramp_start": "2025-05-13T09:30:00+05:30",
  "ramp_peak": "2025-05-13T10:15:00+05:30",
  "ramp_end": "2025-05-13T14:00:00+05:30"
}
```

Verified against the real consumer, not just asserted:

```powershell
cd ..\casper-module-c
.\.venv\Scripts\python.exe -c "from pathlib import Path; from policy.predictive_policy import load_prediction; print(load_prediction(Path('../module-b-estimation/predictions/cbse_class12_2025.json')))"
```

Module C parses it unmodified.

---

## API

```python
import estimate

events      = estimate.load_events()                     # shipped samples
predictions = estimate.predict_all(events)               # resolves priors within the set
prediction  = estimate.predict(event, prior_events=[])   # one event
path        = estimate.write_prediction(prediction)      # -> predictions/<event_id>.json
```

---

## Tests

Built test-first. 19 tests, no mocks.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

The two that matter most:

- **`test_the_documented_example_yields_the_documented_replica_count`** — pins
  the calibration to the 12-replica figure printed in the interim review.
- **`test_predict_reproduces_the_documented_prediction_exactly`** — the
  end-to-end anchor: the Event printed in the docs must produce the Prediction
  printed in the docs, field for field. If anyone retunes a constant, this
  test says so immediately.

---

## Phase II

The interim review lists linear regression and LSTM as alternatives. Both need
historical load to train on, which is the exact thing these portals do not
have — so they are not a drop-in upgrade, they are a different problem. The
honest Phase II step is a wider event dataset and a sourced concurrency rate,
not a bigger model.

---

## Files

```
module-b-estimation/
├── estimate.py                   The model + CLI
├── search_interest_sample.csv    Synthetic search-interest curve (timing signal)
├── sample_events.json            Hand-authored Events, so B runs standalone
├── predictions/                  Generated Predictions, one JSON per event
├── tests/test_estimate.py
├── requirements.txt              pytest (dev only — the model is stdlib-only)
└── README.md
```
