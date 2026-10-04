# CASPER

**Civic-event-Aware Scheduling for Predictive Elastic Resources**

B.Tech ER · ERD415 Project Phase I · Batch 11 · St. Joseph's College of
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

Everything runs locally. No cloud account, no API key, no live external APIs.
The only network call at demo time is the dashboard's webfont request to
Google Fonts, which degrades to system fonts if it fails. Docker images and the
k6 binary are fetched once, up front.

---

## Repository layout

```
CASPER/
├── run-demo.ps1              One-command launcher: menu, demo, experiment, cleanup
├── launcher/                 The launcher's interactive menu + its Pester tests
├── module-a-ingestion/       Module A — event dataset + loader
├── module-b-estimation/      Module B — traffic-magnitude estimation model
├── casper-module-c/          Module C — scale controller + predictive scheduler
├── module-d-evaluation/      Module D — reactive baseline + k6 + comparison
└── dashboard/                Live demo dashboard (React + Tailwind, served by Flask)
```

Each module has its own README with setup, run instructions and design notes.

---

## The four modules

| Module | Owns | Tests |
|---|---|---|
| **A** | Offline civic-event dataset (synthetic sample data) + validating loader | 17 |
| **B** | Traffic-magnitude estimation — turns an Event into a Prediction. *Primary contribution* | 19 |
| **C** | Shared scale controller (Docker + nginx), the predictive policy, the demo portal | 4 (portal) + live runs |
| **D** | Reactive baseline scaler, k6 load test, reactive-vs-predictive comparison | 74 |
| dashboard | Read-only live view of all of the above, in plain language: overview, event schedule, live system, experiment, how it works | 18 backend + 72 frontend |

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

Every module was built test-first. Run all suites from the repo root:

```powershell
foreach ($m in "module-a-ingestion","module-b-estimation","casper-module-c","module-d-evaluation","dashboard") {
    & ".\$m\.venv\Scripts\python.exe" -m pytest ".\$m\tests" -q
}
cd dashboard\frontend; npm test; cd ..\..        # the dashboard's UI tests (vitest)
Invoke-Pester .\launcher                          # the launcher's menu (Pester, ships with Windows)
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

## Running it

Prerequisites: Docker Desktop installed (with virtualisation enabled in the
BIOS), Python 3.10+ on PATH. Everything else — virtual environments, pip
caches, the k6 binary — is created **inside the project folder** on first use.
Nothing is installed system-wide.

### The menu — easiest way in

```powershell
.\run-demo.ps1
```

With no arguments the script asks what to run: the live demo (and which event),
the experiment (and how much traffic), just the stack and dashboard, or stop
everything. It confirms before doing anything. Any flag below skips the menu.

### The live demo — the whole pipeline

```powershell
.\run-demo.ps1 -Demo
```

Runs the real pipeline end to end: **Module A** validates the event dataset,
**Module B** turns every event into a Prediction, **Module C** schedules B's
prediction for `cbse_class12_2026` (shifted to fire ~20 s from now, since the
real date is months away), and the dashboard shows capacity arriving **before**
the traffic — from the calendar alone.

### The experiment — reactive vs predictive

```powershell
.\run-demo.ps1 -Compare
```

Module D replays the same exam-day traffic through k6 twice — once with the
reactive baseline scaling, once with CASPER's predictive policy — and writes
the comparison to `module-d-evaluation\results\` (JSON, a markdown table for the
report, and charts) and to the dashboard. About 9 minutes. See
[module-d-evaluation/README.md](module-d-evaluation/README.md).

**Result** (two independent runs, which agreed to within 1 ms on p95):

| | Reactive baseline | CASPER predictive |
|---|---|---|
| p95 response time | 2063 ms | **121 ms** (−94.2%) |
| error rate | 5.18% | **0.00%** |
| successful requests | 93.90% | **100.00%** |
| replica-seconds (cost) | **623** | 706 |

CASPER had its 4 replicas up 14 s *before* the traffic ramp; the reactive
baseline reached 3 replicas 21 s and 5 replicas 42 s *after* it. CASPER pays
for that with ~13% more replica-time — capacity that sat ready before it was
needed.

### Other options

```powershell
.\run-demo.ps1 -NoBrowser                            # stack + dashboard, nothing scheduled
.\run-demo.ps1 -Compare -PeakRps 400                 # the experiment under heavier traffic
.\run-demo.ps1 -Demo -EventId ssc_cgl_result_2026    # a different event from Module A
.\run-demo.ps1 -Demo -Peak 0                         # use Module B's replica count unchanged
.\run-demo.ps1 -Demo -UpIn 20 -DownIn 120 -Peak 4    # custom timings
.\run-demo.ps1 -Replicas 3 -Build                    # rebuild the image, start with 3
.\run-demo.ps1 -Detach                               # launch and exit, leave it running
.\run-demo.ps1 -Stop                                 # tear down whatever is running
```

`-Peak` defaults to 4: Module B's real estimates (12–20 replicas) are a lot of
containers for a laptop. `-Demo` and `-Compare` refuse to run together — both
drive the scaling knob, and two brains on one knob would void the experiment.

`-PeakRps` (default 250) sets the experiment's peak traffic; 400 needs 6
servers. When CASPER plans more than the reactive scaler's usual ceiling of 6,
that ceiling rises to match, so heavier load stays a fair test. Above 400 req/s
the laptop becomes the bottleneck and the script warns.

**It cleans up after itself.** The script stays in the foreground; press Ctrl+C
and it stops the dashboard, the policy, the comparison, every k6 run and
reactive scaler it started, and every container. Teardown also sweeps orphans
— any python running one of CASPER's own scripts from this repo, any k6 from
`module-d-evaluation\tools`, plus whatever holds port 8050 — so a window closed
by hand last time does not linger. It deliberately matches CASPER's entry-point
scripts, not just "anything running from this repo": an editor extension (e.g.
VS Code's Black formatter) running from a project venv is left alone. Startup runs the same sweep first,
so repeated runs never stack up.

Closing the window with the X button instead of Ctrl+C kills the script without
running its cleanup; the next `.\run-demo.ps1` clears the leftovers, or run
`.\run-demo.ps1 -Stop` yourself.

`-NoDashboard`, `-NoBrowser`, `-KeepContainers` also available.
`Get-Help .\run-demo.ps1 -Full` lists everything. If PowerShell blocks the
script: `powershell -ExecutionPolicy Bypass -File .\run-demo.ps1`.

### Or step by step

Each module's README has its own manual steps. The short version:

```powershell
cd module-a-ingestion;  .\.venv\Scripts\python.exe loader.py
cd ..\module-b-estimation;  .\.venv\Scripts\python.exe estimate.py ..\module-a-ingestion\events.json
cd ..\casper-module-c;  docker compose build;  .\.venv\Scripts\python.exe controller\scale_controller.py 2
.\.venv\Scripts\python.exe scripts\make_demo_prediction.py --source ..\module-b-estimation\predictions\cbse_class12_2026.json --up-in 20 --down-in 120 --peak 4
.\.venv\Scripts\python.exe policy\predictive_policy.py policy\demo_prediction.json
```

> Turn the dashboard's latency probe **off** before any k6 run you start by
> hand, so its own requests do not pollute the measured numbers. `-Compare`
> does this for you.

---

## Design decisions

Flag before re-litigating — each of these has a reason behind it:

1. **Static nginx config rewrite, not dynamic DNS routing.** Produces an
   auditable diff of what changed and when, which is a required deliverable.
   Also avoids open-source nginx caching upstream hostnames at startup.
2. **Portal containers are never published to the host** (`expose`, not
   `ports`) — all traffic goes through nginx on 8080.
3. **Replica health is re-derived from Docker after every scale action**, never
   assumed from the requested N. A container that failed to start must not be
   added to nginx.
4. **Every scale action is logged with a `source` field** (`predictive`,
   `reactive`, `manual`) — it is how Module D separates the two brains.
5. **`predicted_peak_replicas` is in replica units.** Module B does the
   conversion and documents the assumption; Module C consumes it as-is.
6. **Each portal replica has a real capacity limit** — 5 concurrent requests,
   queue up to 2 s, then 503 (~4200 req/min, matching the documented basis).
   Without it, extra load barely moves latency, a latency-driven reactive
   scaler has nothing to react to, and the experiment cannot show a difference.
7. **The reactive baseline is honest, not handicapped.** Its guards
   (consecutive breaches, cooldown, min/max) are standard auto-scaler practice.
   Its only real weakness is the one the project is about: it reacts to load
   that has already arrived.
8. **pandas where it earns its place.** Module D buckets tens of thousands of
   k6 samples with it; Module B's formula is arithmetic over six records and
   stays stdlib-only.

---

## Note on `nginx/nginx.conf`

It is a **generated** file — the controller rewrites it on every scaling action —
but it is committed anyway so a fresh clone can `docker compose up` without a
bootstrap step. Expect it to show as modified after a demo; that churn does not
need to be committed. Edit `nginx/nginx.conf.template` instead, never the
generated file.
