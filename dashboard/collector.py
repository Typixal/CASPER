"""Build dashboard snapshots from the artifacts the system already writes.

Read-only. Sources:
    docker compose ps          replicas and their health
    nginx/nginx.conf           replicas nginx routes to
    logs/scale_actions.jsonl   audit trail
    policy/*.json              the active Prediction
    Module A/B/D outputs       events, forecasts, experiment results
    http://localhost:8080      optional one-request latency probe
"""

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MODULE_C_DIR = REPO_ROOT / "casper-module-c"
NGINX_CONF = MODULE_C_DIR / "nginx" / "nginx.conf"
SCALE_LOG = MODULE_C_DIR / "logs" / "scale_actions.jsonl"
SAMPLE_PREDICTION = MODULE_C_DIR / "policy" / "sample_prediction.json"
DEMO_PREDICTION = MODULE_C_DIR / "policy" / "demo_prediction.json"

MODULE_A_EVENTS = REPO_ROOT / "module-a-ingestion" / "events.json"
MODULE_B_PREDICTIONS_DIR = REPO_ROOT / "module-b-estimation" / "predictions"
MODULE_D_RESULTS_DIR = REPO_ROOT / "module-d-evaluation" / "results"
MODULE_D_K6_DIR = REPO_ROOT / "module-d-evaluation" / "k6"

PORTAL_ENTRYPOINT = "http://localhost:8080"

# Audit-log lines and probe samples kept on screen.
MAX_ACTIONS = 25
PROBE_HISTORY = 90

BEGIN_MARKER = "# --- BEGIN AUTO-GENERATED SERVERS ---"
END_MARKER = "# --- END AUTO-GENERATED SERVERS ---"
# What the controller writes when the stack is drained to zero.
DRAINED_PLACEHOLDER = "127.0.0.1:1"

# Rolling probe history, shared across collections.
_probe_history = deque(maxlen=PROBE_HISTORY)


def _run(cmd, cwd, timeout=15):
    """Run a command without raising.

    Returns:
        (ok, stdout, stderr).
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode == 0, proc.stdout, proc.stderr
    except FileNotFoundError:
        return False, "", "docker CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "", "docker command timed out"
    except OSError as exc:
        return False, "", str(exc)


def _parse_ps_json(raw):
    """Parse `docker compose ps --format json` (array or one object per line)."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def read_docker_state():
    """Read portal replicas and nginx status from Docker.

    Returns:
        Dict with available, error, replicas (name, id, state, health, ready)
        and nginx_running.
    """
    state = {
        "available": False,
        "error": None,
        "replicas": [],
        "nginx_running": False,
    }

    if not MODULE_C_DIR.exists():
        state["error"] = "Module C folder not found at {}".format(MODULE_C_DIR)
        return state

    ok, out, err = _run(
        ["docker", "compose", "ps", "--all", "--format", "json"],
        cwd=MODULE_C_DIR,
    )
    if not ok:
        # Usually Docker Desktop is not running.
        state["error"] = (err or "docker compose ps failed").strip().splitlines()[-1]
        return state

    state["available"] = True
    for row in _parse_ps_json(out):
        service = str(row.get("Service", ""))
        name = row.get("Name") or row.get("Names") or ""
        status = str(row.get("State", "")).lower()
        health = str(row.get("Health", "")).lower()

        if service == "nginx":
            state["nginx_running"] = status == "running"
            continue
        if service != "portal":
            continue

        state["replicas"].append(
            {
                "name": name,
                "short_name": name.split("-")[-1] if name else "?",
                # Matches the portal's served_by (its HOSTNAME = short ID).
                "id": str(row.get("ID", ""))[:12],
                "state": status,
                # "" means no healthcheck; say so instead of implying healthy.
                "health": health or ("no healthcheck" if status == "running" else ""),
                "ready": status == "running" and health in ("healthy", "", "none"),
            }
        )

    state["replicas"].sort(key=lambda r: r["name"])
    return state


def read_nginx_upstream():
    """Read the upstream servers from the generated nginx.conf.

    Returns:
        Dict with exists, servers ("name:port"), drained, modified and error.
    """
    info = {
        "exists": NGINX_CONF.exists(),
        "servers": [],
        "drained": False,
        "modified": None,
        "error": None,
    }
    if not info["exists"]:
        info["error"] = "nginx.conf not generated yet"
        return info

    try:
        text = NGINX_CONF.read_text(encoding="utf-8")
        info["modified"] = datetime.fromtimestamp(
            NGINX_CONF.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    except OSError as exc:
        info["error"] = str(exc)
        return info

    match = re.search(
        re.escape(BEGIN_MARKER) + r"(.*?)" + re.escape(END_MARKER),
        text,
        re.DOTALL,
    )
    if not match:
        info["error"] = "auto-generated markers not found in nginx.conf"
        return info

    for line in match.group(1).splitlines():
        line = line.strip()
        if not line.startswith("server "):
            continue
        target = line[len("server ") :].rstrip(";").split()[0]
        if target == DRAINED_PLACEHOLDER:
            info["drained"] = True
            continue
        info["servers"].append(target)

    return info


def read_scale_actions():
    """Read the audit log.

    Returns:
        Dict with the newest MAX_ACTIONS actions (newest first), total,
        by_source counts, last action and error.
    """
    info = {
        "exists": SCALE_LOG.exists(),
        "actions": [],
        "total": 0,
        "by_source": {},
        "last": None,
        "error": None,
    }
    if not info["exists"]:
        return info

    try:
        lines = SCALE_LOG.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        info["error"] = str(exc)
        return info

    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    info["total"] = len(entries)
    for entry in entries:
        source = entry.get("source", "unknown")
        info["by_source"][source] = info["by_source"].get(source, 0) + 1

    info["actions"] = entries[-MAX_ACTIONS:][::-1]
    if entries:
        info["last"] = entries[-1]
    return info


def _pick_prediction_file():
    """Pick the Prediction the policy is most likely running.

    The demo copy wins when it is at least as new as the sample fixture.

    Returns:
        (path, kind) or (None, None).
    """
    if DEMO_PREDICTION.exists():
        if not SAMPLE_PREDICTION.exists():
            return DEMO_PREDICTION, "demo (time-shifted)"
        if DEMO_PREDICTION.stat().st_mtime >= SAMPLE_PREDICTION.stat().st_mtime:
            return DEMO_PREDICTION, "demo (time-shifted)"
    if SAMPLE_PREDICTION.exists():
        return SAMPLE_PREDICTION, "sample fixture"
    return None, None


def read_prediction():
    """Read the active Prediction and locate now within its window.

    Returns:
        Dict with the prediction fields plus phase (before | ramp | peak |
        after), progress_pct, seconds_to_next and next_action.
    """
    info = {
        "exists": False,
        "file": None,
        "kind": None,
        "error": None,
        "event_id": None,
        "peak_replicas": None,
        "ramp_start": None,
        "ramp_peak": None,
        "ramp_end": None,
        "phase": None,
        "progress_pct": 0.0,
        "seconds_to_next": None,
        "next_action": None,
    }

    path, kind = _pick_prediction_file()
    if path is None:
        return info

    info["exists"] = True
    info["file"] = str(path.relative_to(REPO_ROOT))
    info["kind"] = kind

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        start = datetime.fromisoformat(raw["ramp_start"])
        peak = datetime.fromisoformat(raw["ramp_peak"])
        end = datetime.fromisoformat(raw["ramp_end"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        info["error"] = "could not read prediction: {}".format(exc)
        return info

    info["event_id"] = raw.get("event_id")
    info["peak_replicas"] = raw.get("predicted_peak_replicas")
    info["ramp_start"] = start.isoformat()
    info["ramp_peak"] = peak.isoformat()
    info["ramp_end"] = end.isoformat()

    now = datetime.now(timezone.utc)
    start_utc = start.astimezone(timezone.utc)
    peak_utc = peak.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    if now < start_utc:
        info["phase"] = "before"
        info["next_action"] = "scale UP to {}".format(info["peak_replicas"])
        info["seconds_to_next"] = (start_utc - now).total_seconds()
    elif now < end_utc:
        info["phase"] = "peak" if now >= peak_utc else "ramp"
        info["next_action"] = "scale DOWN"
        info["seconds_to_next"] = (end_utc - now).total_seconds()
        span = (end_utc - start_utc).total_seconds()
        if span > 0:
            info["progress_pct"] = min(
                100.0, max(0.0, (now - start_utc).total_seconds() / span * 100.0)
            )
    else:
        info["phase"] = "after"
        info["progress_pct"] = 100.0

    return info


def probe_portal(enabled=True):
    """Send one request through nginx and record latency and the serving replica.

    Args:
        enabled: When False, return an empty sample without sending anything.

    Returns:
        The sample dict; also appended to the rolling history.
    """
    sample = {
        "enabled": enabled,
        "ok": False,
        "status": None,
        "latency_ms": None,
        "served_by": None,
        "error": None,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    if not enabled:
        return sample

    started = time.perf_counter()
    try:
        request = urllib.request.Request(
            PORTAL_ENTRYPOINT + "/results",
            headers={"User-Agent": "casper-dashboard-probe"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            sample["status"] = response.status
            sample["ok"] = 200 <= response.status < 300
            try:
                sample["served_by"] = json.loads(body).get("served_by")
            except json.JSONDecodeError:
                pass
    except urllib.error.HTTPError as exc:
        # 502 is expected when the stack is drained.
        sample["status"] = exc.code
        sample["error"] = "HTTP {}".format(exc.code)
    except (urllib.error.URLError, OSError) as exc:
        sample["error"] = str(getattr(exc, "reason", exc))

    sample["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    _probe_history.append(
        {
            "at": sample["at"],
            "latency_ms": sample["latency_ms"] if sample["ok"] else None,
            "ok": sample["ok"],
            "served_by": sample["served_by"],
        }
    )
    return sample


def probe_summary():
    """Summarise the probe history.

    Returns:
        Dict with history, samples, per_replica hit counts, avg_ms, max_ms
        and error_count.
    """
    history = list(_probe_history)
    latencies = [h["latency_ms"] for h in history if h["ok"] and h["latency_ms"]]
    per_replica = {}
    for h in history:
        if h["served_by"]:
            per_replica[h["served_by"]] = per_replica.get(h["served_by"], 0) + 1

    summary = {
        "history": history,
        "samples": len(history),
        "per_replica": per_replica,
        "avg_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "max_ms": max(latencies) if latencies else None,
        "error_count": sum(1 for h in history if not h["ok"]),
    }
    return summary


def read_other_modules():
    """Report what Modules A, B and D have produced so far.

    Returns:
        {"a": ..., "b": ..., "d": ...}, each with built, path and detail;
        a missing module reports built=False.
    """
    modules = {}

    a = {"built": MODULE_A_EVENTS.exists(), "path": str(MODULE_A_EVENTS), "detail": None}
    if a["built"]:
        try:
            data = json.loads(MODULE_A_EVENTS.read_text(encoding="utf-8"))
            events = data if isinstance(data, list) else data.get("events", [])
            a["detail"] = "{} event(s)".format(len(events))
            a["events"] = [
                {
                    "event_id": e.get("event_id"),
                    "board": e.get("board"),
                    "date": e.get("date"),
                    "registered_candidates": e.get("registered_candidates"),
                }
                for e in events[:5]
            ]
        except (OSError, ValueError, AttributeError) as exc:
            a["detail"] = "unreadable: {}".format(exc)
    modules["a"] = a

    b = {"built": False, "path": str(MODULE_B_PREDICTIONS_DIR), "detail": None}
    if MODULE_B_PREDICTIONS_DIR.is_dir():
        files = sorted(MODULE_B_PREDICTIONS_DIR.glob("*.json"))
        b["built"] = bool(files)
        b["detail"] = "{} prediction file(s)".format(len(files))
        b["files"] = [f.name for f in files[:5]]
    modules["b"] = b

    d = {"built": False, "path": str(MODULE_D_RESULTS_DIR), "detail": None}
    k6_scripts = sorted(MODULE_D_K6_DIR.glob("*.js")) if MODULE_D_K6_DIR.is_dir() else []
    results = (
        sorted(MODULE_D_RESULTS_DIR.glob("*.json")) if MODULE_D_RESULTS_DIR.is_dir() else []
    )
    d["built"] = bool(k6_scripts or results)
    if d["built"]:
        d["detail"] = "{} k6 script(s), {} result file(s)".format(
            len(k6_scripts), len(results)
        )
        d["k6_scripts"] = [f.name for f in k6_scripts[:5]]
        d["results"] = [f.name for f in results[:5]]
    d["comparison"] = read_comparison()
    modules["d"] = d

    return modules


def read_comparison():
    """Read headline numbers from Module D's comparison.json.

    Omits the time series to keep each SSE push small.

    Returns:
        Per-strategy p95/error/success/replica-seconds plus verdict and
        p95_reduction_pct, or None if the file is missing or half-written.
    """
    path = MODULE_D_RESULTS_DIR / "comparison.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        headline = {}
        for name in ("reactive", "predictive"):
            run = data["strategies"][name]
            headline[name] = {
                "p95_ms": run["summary"]["p95_ms"],
                "error_rate": run["summary"]["error_rate"],
                "success_pct": run["summary"]["success_pct"],
                "replica_seconds": run["replica_seconds"],
            }
        headline["verdict"] = data["verdict"]
        headline["p95_reduction_pct"] = data["p95_reduction_pct"]
        return headline
    except (OSError, ValueError, KeyError, TypeError):
        return None


def collect(probe_enabled=True):
    """Build one complete dashboard snapshot.

    Args:
        probe_enabled: Whether to send the latency probe request.

    Returns:
        The snapshot dict pushed to the browser.
    """
    docker_state = read_docker_state()
    nginx = read_nginx_upstream()
    actions = read_scale_actions()

    prediction = read_prediction()

    ready = [r for r in docker_state["replicas"] if r["ready"]]
    # Healthy but not routed = the controller has not run since it appeared.
    routed = set(s.split(":")[0] for s in nginx["servers"])
    for replica in docker_state["replicas"]:
        replica["routed"] = replica["name"] in routed

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "docker": docker_state,
        "summary": {
            "replicas_total": len(docker_state["replicas"]),
            "replicas_ready": len(ready),
            "replicas_routed": len(nginx["servers"]),
            "drained": nginx["drained"],
            "last_source": (actions["last"] or {}).get("source"),
        },
        "nginx": nginx,
        "scale_log": actions,
        "prediction": prediction,
        "schedule": read_schedule(
            demo_event_id=prediction.get("event_id")
            if "demo" in (prediction.get("kind") or "")
            else None
        ),
        "probe": probe_portal(probe_enabled),
        "probe_summary": probe_summary(),
        "modules": read_other_modules(),
        "paths": {
            "repo_root": str(REPO_ROOT),
            "module_c": str(MODULE_C_DIR),
            "entrypoint": PORTAL_ENTRYPOINT,
        },
    }


def read_schedule(now=None, demo_event_id=None):
    """Join Module A's events with Module B's forecasts, in date order.

    Args:
        now: Reference time for past/upcoming. Defaults to the current time.
        demo_event_id: Event the live demo is replaying, flagged demo=True.

    Returns:
        Rows with event_id, board, event_type, date, registered_candidates,
        predicted_peak_replicas, ramp_start, ramp_end (None without a
        forecast), status ("past" | "upcoming") and demo.
    """
    now = now or datetime.now(timezone.utc)
    try:
        data = json.loads(MODULE_A_EVENTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    events = data if isinstance(data, list) else data.get("events", [])

    rows = []
    for e in events:
        try:
            date = datetime.fromisoformat(e["date"])
        except (KeyError, TypeError, ValueError):
            continue  # invalid date: skip rather than break the page

        forecast = {}
        path = MODULE_B_PREDICTIONS_DIR / "{}.json".format(e.get("event_id"))
        try:
            forecast = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

        rows.append(
            {
                "event_id": e.get("event_id"),
                "board": e.get("board"),
                "event_type": e.get("event_type"),
                "date": e["date"],
                "registered_candidates": e.get("registered_candidates"),
                "predicted_peak_replicas": forecast.get("predicted_peak_replicas"),
                "ramp_start": forecast.get("ramp_start"),
                "ramp_end": forecast.get("ramp_end"),
                "status": "past" if date < now else "upcoming",
                "demo": e.get("event_id") == demo_event_id,
                "_sort": date,
            }
        )

    rows.sort(key=lambda r: r["_sort"])
    for r in rows:
        del r["_sort"]
    return rows
