# CASPER

**Civic-event-Aware Scheduling for Predictive Elastic Resources**

B.Tech ECE · ERD415 Project Phase I · Batch 11 · St. Joseph's College of
Engineering and Technology, Palai

---

## The problem

Indian government exam-result and admission portals crash on known
high-traffic dates. Conventional predictive auto-scalers forecast demand from an
application's *own historical traffic* — but a portal that is idle 364 days a
year and hit by one massive spike on one known date has no history to learn
from.

CASPER replaces *"watch live traffic and react"* with *"know the event date in
advance and provision for it"*, using proxy signals — registered candidate
counts, comparable past events, search-interest shape — instead of historical
load.

The experiment: **same infrastructure, same traffic curve, two different brains
deciding when to scale.** A conventional reactive auto-scaler versus CASPER's
calendar-driven predictive scheduler.

Everything runs locally. No cloud account, no API key, no internet at demo time
(aside from one-time Docker image pulls).

---

## Repository layout

```
CASPER/
├── casper-module-c/          Module C — scale controller + predictive scheduler   [BUILT]
├── dashboard/                Live demo dashboard                                  [BUILT]
├── module-a-ingestion/       Module A — event dataset + loader                    [not built]
├── module-b-estimation/      Module B — traffic-magnitude estimation model        [not built]
└── module-d-evaluation/      Module D — reactive baseline + k6 + comparison       [not built]
```

Each module has its own README with setup and run instructions.

---

## The four modules

| Module | Owns | Status |
|---|---|---|
| **A** | Offline civic-event dataset (exam boards, result dates, candidate counts) + loader | Not built |
| **B** | Traffic-magnitude estimation — turns an Event into a Prediction. *Primary contribution* | Not built |
| **C** | Shared scale controller (Docker + nginx) and the predictive policy on top of it | **Built and tested** |
| **D** | Reactive baseline scaler, k6 load tests, comparison metrics | Not built |

```
[Event Calendar Data] → INGESTION (A) → [Event + Metadata]
                                              ↓
                              TRAFFIC ESTIMATION MODEL (B)
                                              ↓
                              [Predicted Peak + Time Window]
                                              ↓
                  PRE-PROVISIONING SCHEDULER (C) ──┐
                                                   ├─→ SHARED SCALE CONTROLLER (C)
                  REACTIVE BASELINE SCALER (D) ────┘    (Docker Compose + nginx)
                                              ↓
                              DEMONSTRATOR / LOAD TEST — k6 (D)
```

---

## Frozen schemas — the inter-module contracts

These do not change without whole-team agreement. Code that needs a change
should flag it in a comment rather than diverge silently.

**Event** (A produces → B consumes)

```json
{
  "event_id": "cbse_class12_2025",
  "board": "CBSE",
  "event_type": "exam_result",
  "date": "2025-05-13T10:00:00+05:30",
  "registered_candidates": 1650000,
  "prior_similar_event_ids": ["cbse_class12_2024"]
}
```

**Prediction** (B produces → C consumes)

```json
{
  "event_id": "cbse_class12_2025",
  "predicted_peak_replicas": 12,
  "ramp_start": "2025-05-13T09:30:00+05:30",
  "ramp_peak": "2025-05-13T10:15:00+05:30",
  "ramp_end": "2025-05-13T14:00:00+05:30"
}
```

All timestamps are ISO 8601 with a timezone offset (IST, `+05:30`).
`predicted_peak_replicas` is in container-replica units, not concurrent users
(documented basis: ~4000 req/min per replica).

---

## Running the demo today

Prerequisites: Docker Desktop running, Python 3.10+.

**1 — bring up the stack and scale it manually**

```powershell
cd casper-module-c
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose build
.\.venv\Scripts\python.exe controller\scale_controller.py 3
```

`curl.exe http://localhost:8080/results` a few times — the `served_by` field
changes, proving nginx is spreading load across the three replicas.

**2 — start the dashboard** (separate terminal)

```powershell
cd dashboard
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open <http://localhost:8050>.

**3 — run the predictive policy** (third terminal)

```powershell
cd casper-module-c
.\.venv\Scripts\python.exe scripts\make_demo_prediction.py --up-in 20 --down-in 120 --peak 4
.\.venv\Scripts\python.exe policy\predictive_policy.py policy\demo_prediction.json
```

Watch the dashboard: the countdown runs, then replicas appear **while the
timeline is still in the "before" phase** — capacity provisioned ahead of the
traffic, from the calendar alone. At `ramp_end` it drains back down.

> Turn the dashboard's latency probe **off** before any Module D k6 run, so its
> own requests do not pollute the measured numbers. See `dashboard/README.md`.

---

## Build order for the remaining modules

1. ~~Freeze the Event and Prediction schemas~~ — done.
2. ~~Module C, scale controller standalone~~ — done.
3. In parallel: **A** (dataset + loader), **B** (estimation model), **D** (k6
   scripts against a manually scaled portal — do not wait on B or C's policy).
4. ~~Module C, predictive policy~~ — done.
5. **D**: reactive baseline calling `scale_to(n, source="reactive")` from
   Module C's controller.
6. Integration: full pipeline, Event → Prediction → predictive vs reactive → k6
   comparison.

### For whoever builds Module D

```python
import sys
sys.path.insert(0, "../casper-module-c")
from controller.scale_controller import scale_to, current_replica_count

scale_to(5, source="reactive")   # always tag the source
```

That `source` tag is what separates "CASPER scaled this" from "the baseline
scaled this" in the audit log and on the dashboard. Importing the controller is
side-effect free. k6 must target `http://localhost:8080`, never a portal
container directly.

---

## Design decisions already made

Flag before re-litigating — each of these has a reason behind it:

1. **Static nginx config rewrite, not dynamic DNS routing.** Produces an
   auditable diff of what changed and when, which is a required deliverable.
   Also avoids open-source nginx caching upstream hostnames at startup.
2. **Portal containers are never published to the host** (`expose`, not
   `ports`) — all traffic goes through nginx on 8080.
3. **Replica health is re-derived from Docker after every scale action**, never
   assumed from the requested N. A container that failed to start must not be
   added to nginx.
4. **Every scale action is logged with a `source` field** from the start — it is
   infrastructure for Module D's comparison, not optional logging.
5. **`predicted_peak_replicas` is in replica units.** Module B does the
   conversion and documents the assumption; Module C consumes it as-is.

---

## Note on `nginx/nginx.conf`

It is a **generated** file — the controller rewrites it on every scaling action —
but it is committed anyway so a fresh clone can `docker compose up` without a
bootstrap step. Expect it to show as modified after a demo; that churn does not
need to be committed. Edit `nginx/nginx.conf.template` instead, never the
generated file.
