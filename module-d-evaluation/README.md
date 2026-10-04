# CASPER — Module D

**Reactive Baseline, Load Test & Evaluation**

The thing CASPER has to beat, and the proof that it does. This module runs the
experiment the whole project exists for:

> Same traffic, same infrastructure, same scale controller —
> two different brains deciding when to scale.

```
                 ┌─ run 1: reactive baseline ─┐
exam-day curve ──┤                            ├─→ comparison.json / .md / charts
   (k6)          └─ run 2: CASPER predictive ─┘        └─→ dashboard panel
```

---

## Run it

The one-command way, from the repo root (needs Docker running):

```powershell
.\run-demo.ps1 -Compare
```

That creates the venv, fetches k6 if missing, starts the stack and dashboard
(with the dashboard's own latency probe **off**, so it adds no traffic to the
measurement), and runs the comparison in its own window. About 9 minutes.
Ctrl+C in the launcher window cleans everything up — scalers, k6, containers.

By hand:

```powershell
cd D:\Projects\CASPER\module-d-evaluation
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File tools\fetch_k6.ps1      # one time

.\.venv\Scripts\python.exe run_comparison.py --dry-run           # see the plan
.\.venv\Scripts\python.exe run_comparison.py                     # the real run
```

The reactive scaler on its own, against a running stack:

```powershell
.\.venv\Scripts\python.exe reactive_baseline.py --help
```

---

## The experiment

### The traffic curve — identical for both runs

`traffic.py` → `k6/exam_day_traffic.js`

| Phase | Duration | Load |
|---|---|---|
| quiet | 45 s | 5% of peak — candidates idling before publication |
| ramp | 20 s | climbs to peak — the result goes live |
| peak | 90 s | 250 req/s sustained |
| decay | 45 s | tails off to 10% |

k6 uses the **`ramping-arrival-rate`** executor: requests keep arriving on
schedule whether or not the portal keeps up, like candidates hammering refresh.
That is what makes under-provisioning visible — as latency and errors — instead
of the load generator politely slowing down to match a struggling server.

Sized for a laptop: the peak needs **4 replicas** at the project's documented
~4000 req/min per replica. (Module B's estimates for the real events are 12–20
replicas — the conversion is the same, only the magnitude is scaled down.)

### Run 1 — the reactive baseline

`reactive_baseline.py` is an **honest** stand-in for a conventional
latency-driven auto-scaler. Every 5 s it sends 8 concurrent requests through
nginx and takes the p95:

| Rule | Value |
|---|---|
| scale up | +2 replicas after **2 consecutive** probes with p95 > 400 ms |
| scale down | −1 replica after **6 consecutive** probes with p95 < 150 ms |
| cooldown | 15 s after any scale action — new replicas need time to pass healthchecks |
| bounds | 1 – 6 replicas |

Every one of those guards is standard practice in real auto-scalers, not a
handicap added to flatter CASPER. A failed probe (e.g. a 503 from a saturated
replica) is scored at the full timeout, because a fast refusal recorded at face
value would make an overloaded portal look quick.

Its one genuine weakness is the one the project is about: **it can only react
to load that has already arrived.**

### Run 2 — CASPER predictive

Module C's real `predictive_policy.py`, handed a Prediction aligned to the k6
run: scale to 4 replicas **20 s before the ramp starts**, from the calendar
alone. 20 s covers the time new containers take to pass their healthcheck.

### What makes it a fair test

- **Same knob.** Both strategies call Module C's `scale_to()` — the reactive
  scaler through `module_c.py`, which imports the real controller.
- **Same start.** The portal is reset to 1 replica before each run.
- **Same traffic.** One stages file, written once, used for both k6 runs.
- **Real capacity.** Each portal replica serves at most 5 requests at once
  (queue 2 s, then 503) — see Module C. Without that cap, extra load barely
  moves latency and there would be nothing to compare.
- **Cleanup is unconditional.** A scaler is stopped even if k6 crashes, so
  nothing keeps resizing the stack after the run.

---

## Output

```
results/
├── comparison.json        everything, machine-readable (the dashboard reads this)
├── comparison.md          the table for the report
├── latency_over_time.png  p95 per 5 s for both runs, with replica count beneath
├── summary_bars.png       p95 / error rate / success %, side by side
└── raw/                   k6 CSVs, summaries, scaler logs (gitignored)
```

The three headline metrics are the project's committed needs metrics:
**response time, error rate, % successful requests.** Two more for honesty:

- **Dropped** — requests k6 could not even send on schedule. These count as
  *unsuccessful* in the success %, otherwise the more overloaded strategy would
  look better.
- **Replica-seconds** — area under the replica-count curve, a cost proxy.
  CASPER provisions *before* the traffic, so some of that capacity sits idle
  first. Reporting it keeps the comparison honest about the trade-off.

---

## Why pandas here (and not in Module B)

Bucketing tens of thousands of raw k6 samples into per-5-second p95 and error
rates is exactly what a dataframe is for. Module B's formula is arithmetic over
six records, so it stays stdlib-only. Each module uses the tool its job needs.

---

## Tests

Built test-first: **67 tests**, each written and watched fail before the code
that satisfies it. No mocks.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

- The k6 fixtures are **real k6 v2.3.0 output**, not hand-written guesses at
  the format. That caught a real trap: in k6's `http_req_failed`, the `passes`
  field counts *failures*. Reading it as successes would have inverted the
  project's headline result.
- The probe tests run against a real local HTTP server.
- The orchestrator is tested through an injected environment (the boundary it
  is designed to be handed), with the real k6 fixtures flowing through the
  whole comparison pipeline downstream.

Not unit-tested, because they need Docker: `RealEnvironment` in
`run_comparison.py` and `main()` in `reactive_baseline.py`. Both are thin
wiring — every decision they make goes through tested code.

---

## Files

```
module-d-evaluation/
├── reactive_baseline.py   the baseline scaler: decision rule, control loop, CLI
├── probe.py               concurrent latency probe + nearest-rank percentile
├── traffic.py             the exam-day curve, as k6 stages
├── k6/exam_day_traffic.js the load test
├── run_comparison.py      the orchestrator (+ --dry-run)
├── compare.py             k6 output → summary, time series, verdict, reports
├── charts.py              matplotlib charts for the report
├── module_c.py            bridge to Module C's real scale controller
├── tools/fetch_k6.ps1     downloads a pinned k6.exe into tools/ (nothing system-wide)
├── tests/                 67 tests + real k6 fixtures
├── results/               output (raw/ is gitignored)
└── requirements.txt       pandas, matplotlib, pytest (pyparsing pinned — see file)
```
