# CASPER — Module C

**Shared Scale Controller + Predictive Scheduler**

CASPER (Civic-event-Aware Scheduling for Predictive Elastic Resources) provisions
capacity for a government exam-result portal from the *calendar* instead of from
live traffic. Module C builds two things:

1. **The scale controller** — the shared "knob" that changes how many portal
   containers are running and keeps nginx pointed at the healthy ones. Both
   scaling strategies in the project call into this one file.
2. **The predictive policy** — the CASPER brain. It reads a Prediction from
   Module B and scales **up before the event starts**, then back down gracefully
   after it ends.

Everything runs on one laptop. No cloud account, no API key, no internet at
runtime (aside from the one-time Docker image pulls).

---

## 1. Prerequisites

- **Docker Desktop**, installed *and running* (whale icon in the system tray).
  Check with:
  ```
  docker compose version
  docker info
  ```
  If `docker info` errors with "cannot find the file specified", Docker Desktop
  is not started yet — start it and wait for it to say "Engine running".
- **Python 3.10+** on the host.

### Python setup (one time)

The predictive policy runs on the host, not in a container, so it needs
APScheduler. A virtual environment inside this folder keeps it off the C: drive
and out of the system Python:

```powershell
cd D:\Projects\CASPER\casper-module-c
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then use `.\.venv\Scripts\python.exe` wherever this README says `python`
(or activate the venv with `.\.venv\Scripts\Activate.ps1` and just type `python`).

### Build the images (one time, plus after editing `portal/app.py`)

```
docker compose build
```

---

## 2. Milestone 1 — manual scaling (no prediction involved)

This proves the infrastructure works on its own, before Modules A, B and D exist.

```
python controller/scale_controller.py 3
```

What that does, in order: scales the `portal` service to 3 replicas, waits for
Docker to report them healthy, rewrites `nginx/nginx.conf` with the real healthy
replica list, reloads nginx with zero downtime, and appends one line to
`logs/scale_actions.jsonl`.

**Verify load balancing** — run this a few times and watch `served_by` change:

```powershell
curl http://localhost:8080/results
```

(In PowerShell, `curl` is an alias for `Invoke-WebRequest`; use
`curl.exe http://localhost:8080/results` or
`(Invoke-RestMethod http://localhost:8080/results).served_by` for clean output.)

Ten requests at once:

```powershell
1..10 | ForEach-Object { (Invoke-RestMethod http://localhost:8080/results).served_by }
```

**Verify the artifacts:**

- `nginx/nginx.conf` — the `upstream portal_backend` block now lists three
  `server casper-module-c-portal-N:5000;` lines.
- `logs/scale_actions.jsonl` — one JSON line per scaling action:
  ```json
  {"timestamp":"...","action":"scale_to","requested_replicas":3,"actual_healthy_replicas":3,"replica_names":["..."],"source":"manual"}
  ```

Scale down the same way (`python controller/scale_controller.py 1`, or `0` to
fully drain). Scaling to 0 is handled: nginx cannot start with an empty upstream
block, so the controller writes a `server 127.0.0.1:1 down;` placeholder.

---

## 3. Milestone 2 — the predictive policy

The sample prediction (`policy/sample_prediction.json`) uses the real CBSE 2025
result date, which is in the past — so for a demo, generate a copy whose
timestamps are a few seconds from now:

```
python scripts/make_demo_prediction.py --up-in 15 --down-in 90 --peak 4
python policy/predictive_policy.py policy/demo_prediction.json
```

Watch it: at `ramp_start` it scales up to the peak on its own, and at `ramp_end`
it scales back down to the post-event floor. No manual intervention, no live
metric — purely the calendar. Ctrl+C to stop.

`--peak 4` is there because 12 Flask containers is a lot for a laptop; drop it
to use the real predicted peak.

Run against a real (future-dated) prediction with:

```
python policy/predictive_policy.py path/to/prediction.json
```

With no argument it uses `policy/sample_prediction.json`, which will warn that
both actions are in the past and exit — that is expected, and is why the
time-shift script exists.

### The audit trail

The deliverable is "predicted event → planned action → executed action":

- **Predicted event** — the Prediction JSON the policy loaded.
- **Planned action** — the `PLANNED: at <time> scale UP to N replicas` lines the
  policy prints when it schedules the jobs.
- **Executed action** — the matching lines in `logs/scale_actions.jsonl`, tagged
  `"source": "predictive"`.

---

## 4. Notes for other modules

### For whoever builds Module D (reactive baseline)

Import the shared controller and **always pass `source="reactive"`**:

```python
from controller.scale_controller import scale_to, current_replica_count

scale_to(5, source="reactive")
```

That `source` tag is what lets the comparison separate "CASPER scaled this" from
"the reactive baseline scaled this" in `logs/scale_actions.jsonl`. Importing
`scale_controller` is side-effect free — nothing touches Docker at import time.

k6 should target `http://localhost:8080/results` — the nginx entry point, never a
portal container directly.

### For Module B

Module C consumes the frozen **Prediction** schema exactly as specified:

```json
{
  "event_id": "cbse_class12_2025",
  "predicted_peak_replicas": 12,
  "ramp_start": "2025-05-13T09:30:00+05:30",
  "ramp_peak": "2025-05-13T10:15:00+05:30",
  "ramp_end": "2025-05-13T14:00:00+05:30"
}
```

Timestamps must be ISO 8601 with a timezone offset. `predicted_peak_replicas` is
in container replicas, not concurrent users (documented basis: ~4000 req/min per
replica).

---

## 5. Files

```
casper-module-c/
├── portal/
│   ├── app.py                  Flask demo portal (/, /results, /health)
│   ├── Dockerfile
│   └── requirements.txt
├── nginx/
│   ├── nginx.conf.template     EDIT THIS ONE
│   └── nginx.conf              GENERATED — do not hand-edit
├── controller/
│   └── scale_controller.py     Shared scale controller (Module D imports this)
├── policy/
│   ├── predictive_policy.py    The CASPER predictive brain
│   └── sample_prediction.json  Hand-authored test fixture
├── scripts/
│   └── make_demo_prediction.py Demo-only: shifts prediction times to "now"
├── logs/
│   └── scale_actions.jsonl     Audit log, created on first run
├── docker-compose.yml
└── requirements.txt            Host-side deps (APScheduler)
```

> **`nginx/nginx.conf` is a generated file.** The controller overwrites it on
> every scaling action. Edit `nginx/nginx.conf.template` instead — anything you
> type into the generated file is lost on the next scale.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `failed to connect to the docker API ... npipe` | Docker Desktop is not running. Start it, wait for "Engine running". |
| `ModuleNotFoundError: apscheduler` | Use the venv Python: `.\.venv\Scripts\python.exe policy/predictive_policy.py` |
| `curl` prints an HTML-ish object in PowerShell | PowerShell's `curl` is `Invoke-WebRequest`. Use `curl.exe`, or `Invoke-RestMethod`. |
| Controller warns "asked for N but only M are healthy" | A container failed its healthcheck. This is working as intended — nginx is configured with only the M that work. Check `docker compose logs portal`. |
| Port 8080 already in use | Change the host side of `ports: ["8080:80"]` in `docker-compose.yml` (e.g. `8090:80`) and tell Module D the new port. |
| `served_by` never changes | You are likely hitting a cached connection. Send several fresh requests; also confirm `nginx/nginx.conf` really lists more than one server. |
