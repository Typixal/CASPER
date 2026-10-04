# CASPER — Live Demo Dashboard

What the CASPER demo is doing *right now*, explained so that someone with no
cloud background can follow it, with the engineering detail one switch away.

Built for the projector during the Phase I demo. The point it has to make
visible is that **CASPER has servers ready before the students arrive**, while a
normal autoscaler only reacts after the rush has already started.

---

## Pages

A sidebar splits the dashboard into five pages, in story order:

| Page | For | Shows |
|---|---|---|
| **Overview** | anyone — where a viewer lands | One plain sentence on what's happening ("CASPER is getting ready for CBSE Class 12 results 2026"), the key numbers, the countdown, the next event, and the experiment's headline |
| **Event schedule** | anyone | Every event in Module A's dataset with Module B's forecast: date, students registered, servers planned, the get-ready window, past/upcoming, and which event the demo is replaying |
| **Live system** | the curious / evaluators | The machinery: servers over time, each server's health, page-load speed, who changed the server count, the traffic director (nginx) — each panel with a one-line explanation |
| **Experiment** | anyone | Module D's result in plain English ("the slowest page loads were 17× faster"), the results table, why the test is fair, and the report's charts |
| **How it works** | anyone | The problem, the four modules as four plain steps, and a glossary |

The page lives in the URL (`#schedule`, `#experiment`, …), so refreshing — or the
browser's back button — keeps your place mid-demo.

### Plain words by default, technical terms on request

Every label exists twice: a plain word ("servers", "slowest page loads",
"traffic director") and the engineering term ("replicas", "p95 latency",
"nginx upstream"). **Show technical terms** in the sidebar flips the whole
dashboard; the choice is remembered. Both vocabularies live in one table
(`frontend/src/lib/terms.js`), so the two modes can't drift apart, and the
How it works glossary is generated from the same table.

---

## Read-only by design

The dashboard never scales anything, never writes to `nginx.conf`, and never
touches the audit log. It only reads artifacts the system already produces:

| Panel | Source |
|---|---|
| Portal replicas | `docker compose ps` in `casper-module-c/` |
| nginx upstream | `casper-module-c/nginx/nginx.conf` (the generated file) |
| Scale action log | `casper-module-c/logs/scale_actions.jsonl` |
| Prediction window | `casper-module-c/policy/demo_prediction.json`, else `sample_prediction.json` |
| Probe latency | one HTTP request per refresh to `http://localhost:8080/results` |
| Modules A / B / D | presence of their files — greyed out until those modules exist |

Starting or closing it cannot affect a demo in progress. It runs as its own
host process, so `docker-compose.yml` is untouched and the Module C stack
behaves exactly as it did before.

---

## Run it

```powershell
cd D:\Projects\CASPER\dashboard
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Then open <http://localhost:8050>.

The Module C stack should be up (`docker compose up -d` in `casper-module-c/`,
or any `scale_controller.py` run). If Docker is not running, the dashboard still
loads and shows a red banner explaining why — it does not crash.

### Options

| Env var | Default | Meaning |
|---|---|---|
| `CASPER_DASH_PORT` | `8050` | Port the dashboard listens on |
| `CASPER_DASH_REFRESH` | `2` | Seconds between snapshots |
| `CASPER_DASH_PROBE` | `1` | `0` disables the latency probe at startup |

---

## The latency probe — read this before a Module D load test

To show live latency, the dashboard sends **one request every refresh** to
`http://localhost:8080/results`. That is the dashboard's own traffic, labelled as
such on screen, and it is roughly 0.5 req/s.

**Turn it off before running k6 for real numbers** — press the *test visitor*
button on the **Live system** page, or start with `CASPER_DASH_PROBE=0`. Module D's measurements should not
include traffic the dashboard generated. Everything else on the dashboard keeps
working with the probe off; only the latency panel goes quiet.

---

## What to point at during the demo

1. **Overview** — the sentence at the top tells the story; the countdown shows
   when CASPER will add servers, *before* the students arrive.
2. **Event schedule** — where those numbers come from: the event, how many
   students registered, how many servers Module B planned.
3. **Live system** — watch servers appear *while the countdown is still
   running*. That is the whole thesis of the project.
4. **Experiment** — the proof: same visitors twice, 17× faster slowest page
   loads, no failed loads, and the honest cost (13% more server time).

---

## The experiment and the probe lock

Once Module D has run (`.\run-demo.ps1 -Compare`), the Experiment page shows the
result from `module-d-evaluation/results/comparison.json`, plus the report's
charts (served read-only from `results/*.png`). Only the headline numbers travel
over SSE; a missing or half-written file (mid-run) shows how to produce it
instead of breaking the page.

`-Compare` starts the dashboard with its test visitor **off and locked**
(`CASPER_DASH_PROBE=0`, `CASPER_DASH_PROBE_LOCKED=1`): the toggle endpoint
returns 409 and the button reads "test visitor locked off". Off alone was not
enough — one click turned it back on mid-run and added the dashboard's own
requests to the traffic being measured.

---

## Endpoints

| Route | Purpose |
|---|---|
| `/` | The dashboard page |
| `/stream` | Server-sent events — pushes each new snapshot |
| `/api/state` | The current snapshot as JSON (useful for debugging) |
| `/api/probe/toggle` | POST — turns the test visitor on/off (409 while locked) |
| `/api/results/<name>.png` | Module D's report charts, read-only. Only bare `*.png` names; nothing else is servable |

---

## Tests

Built test-first. Two suites:

```powershell
# backend: collector, schedule join, probe lock, chart route
.\.venv\Scripts\python.exe -m pytest tests/ -q          # 18 tests

# frontend: wording, every page, sidebar, routing
cd frontend
npm test                                                # 72 tests (vitest + Testing Library)
```

The frontend tests assert on what a viewer reads — page headings, sentences,
labels in both plain and technical mode — not on markup or chart pixels.
`npm run screenshot` (with the dashboard running) captures every page to
`frontend/screenshots/` for checking by eye; it uses a fixed viewport, because a
full-page capture resizes the window and photographs charts mid-animation.

---

## Files

```
dashboard/
├── app.py                   Flask app, SSE stream, probe lock, chart route
├── collector.py             Reads Docker / nginx.conf / audit log / prediction / schedule
├── tests/                   backend tests (pytest)
├── frontend/                React + Tailwind source (built with Vite)
│   ├── .npmrc               keeps npm's cache inside the project, off C:
│   ├── scripts/             build:flask sync, screenshot tool
│   └── src/
│       ├── App.jsx          sidebar + page routing (URL hash) + technical switch
│       ├── pages/           Overview, Schedule, Live, Experiment, How it works
│       ├── components/      sidebar, panels, charts
│       └── lib/             terms (plain/technical), narrative + comparison wording, SSE hook
├── static/dist/             BUILD OUTPUT — committed, Flask serves this
├── templates/index.html     the Vite-built HTML shell — regenerated, never hand-edited
├── requirements.txt         Flask (+ pytest for development)
└── README.md
```

The demo machine never needs Node — it only ever runs `python app.py` against
the committed `static/dist/`. React, Tailwind, recharts, lucide icons and
framer-motion are compiled into that bundle at build time, so the only live
network call the page makes is the Google Fonts request for Inter and
JetBrains Mono. If that fails the page still renders correctly on system fonts.

### Changing the UI

Edit files under `frontend/src/`, test, then rebuild:

```powershell
cd dashboard\frontend
npm install          # first time only -- cache stays in .npm-cache\ (see .npmrc)
npm test
npm run build:flask  # builds AND copies the result into ../templates/index.html
```

`npm run build:flask` exists so nobody hand-edits the hashed asset filename Vite
generates into `templates/index.html`. Plain `npm run build` updates
`static/dist/` but **not** `templates/index.html`. Restart `python app.py` after
a rebuild — Flask caches the template.
