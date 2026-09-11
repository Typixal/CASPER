"""
CASPER dashboard -- state collector.

Reads the live state of the demo from the artifacts the system already
produces. It is strictly READ-ONLY: nothing in this file scales anything,
writes to nginx, or touches the audit log. The dashboard observes the demo,
it never drives it.

Sources it reads:
    docker compose ps        -> which portal replicas exist and their health
    nginx/nginx.conf         -> which replicas nginx is actually routing to
    logs/scale_actions.jsonl -> the audit trail (who scaled, when, why)
    policy/*.json            -> the Prediction currently driving the policy
    http://localhost:8080    -> a light liveness probe for latency (optional)

Module A / B / D artifacts are looked for too, and simply reported as
"not built yet" when absent.
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

# ---------------------------------------------------------------------------
# Where things live. Repo root is the parent of this dashboard folder.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

MODULE_C_DIR = REPO_ROOT / "casper-module-c"
NGINX_CONF = MODULE_C_DIR / "nginx" / "nginx.conf"
SCALE_LOG = MODULE_C_DIR / "logs" / "scale_actions.jsonl"
SAMPLE_PREDICTION = MODULE_C_DIR / "policy" / "sample_prediction.json"
DEMO_PREDICTION = MODULE_C_DIR / "policy" / "demo_prediction.json"

# Not built yet -- these are the paths from Section 10 of the architecture doc.
# The dashboard lights these panels up automatically if the files ever appear.
MODULE_A_EVENTS = REPO_ROOT / "module-a-ingestion" / "events.json"
MODULE_B_PREDICTIONS_DIR = REPO_ROOT / "module-b-estimation" / "predictions"
MODULE_D_RESULTS_DIR = REPO_ROOT / "module-d-evaluation" / "results"
MODULE_D_K6_DIR = REPO_ROOT / "module-d-evaluation" / "k6"

PORTAL_ENTRYPOINT = "http://localhost:8080"

# How many audit-log lines and probe samples to keep on screen.
MAX_ACTIONS = 25
PROBE_HISTORY = 90

BEGIN_MARKER = "# --- BEGIN AUTO-GENERATED SERVERS ---"
END_MARKER = "# --- END AUTO-GENERATED SERVERS ---"
# The placeholder the controller writes when the stack is drained to zero.
DRAINED_PLACEHOLDER = "127.0.0.1:1"

# Rolling probe history, shared across collections.
_probe_history = deque(maxlen=PROBE_HISTORY)


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
def _run(cmd, cwd, timeout=15):
    """Run a command and return (ok, stdout, stderr). Never raises."""
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
    """
    Parse `docker compose ps --format json`.

    Compose prints either one JSON object per line or a single JSON array
    depending on version, so handle both.
    """
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
    """Ask Docker what is running right now."""
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
        # Most common cause by far: Docker Desktop is not running.
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
                # The portal reports HOSTNAME (= the container's short ID) in
                # its responses, so keep the ID here to match probe replies
                # back to the container that served them.
                "id": str(row.get("ID", ""))[:12],
                "state": status,
                # An image with no healthcheck reports "" -- show that as
                # "no healthcheck" rather than pretending it is healthy.
                "health": health or ("no healthcheck" if status == "running" else ""),
                "ready": status == "running" and health in ("healthy", "", "none"),
            }
        )

    state["replicas"].sort(key=lambda r: r["name"])
    return state


# ---------------------------------------------------------------------------
# nginx
# ---------------------------------------------------------------------------
def read_nginx_upstream():
    """Read which replicas nginx is currently configured to route to."""
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


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def read_scale_actions():
    """Read the tail of the audit log plus a per-source tally."""
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

    info["actions"] = entries[-MAX_ACTIONS:][::-1]  # newest first
    if entries:
        info["last"] = entries[-1]
    return info


# ---------------------------------------------------------------------------
# Prediction (Module B's contract, consumed by Module C's policy)
# ---------------------------------------------------------------------------
def _pick_prediction_file():
    """
    Choose which Prediction the policy is most likely running against.

    demo_prediction.json is the time-shifted copy made for a live demo, so if
    it exists and is newer it wins; otherwise fall back to the hand-authored
    sample fixture.
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
    """Read the active Prediction and work out where we are in its window."""
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


# ---------------------------------------------------------------------------
# Liveness probe (optional)
# ---------------------------------------------------------------------------
def probe_portal(enabled=True):
    """
    Send ONE request to the nginx entry point to measure live latency and see
    which replica answers.

    This is the dashboard's own traffic -- one request per refresh, clearly
    labelled as such in the UI so it is never confused with k6's measurements.
    Can be switched off from the UI before a Module D load test, so it does not
    add noise to the numbers being reported.
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
        # 502 here is meaningful, not a crash: it is what a fully drained
        # stack looks like from outside.
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
    """Latency history and a per-replica hit count from the probe."""
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


# ---------------------------------------------------------------------------
# Modules A / B / D -- present or "not built yet"
# ---------------------------------------------------------------------------
def read_other_modules():
    """
    Report what exists of the other three modules.

    Nothing is faked here. A module that has not been built reports
    built=False and the dashboard greys its panel out.
    """
    modules = {}

    # --- Module A: event dataset ---
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

    # --- Module B: generated predictions ---
    b = {"built": False, "path": str(MODULE_B_PREDICTIONS_DIR), "detail": None}
    if MODULE_B_PREDICTIONS_DIR.is_dir():
        files = sorted(MODULE_B_PREDICTIONS_DIR.glob("*.json"))
        b["built"] = bool(files)
        b["detail"] = "{} prediction file(s)".format(len(files))
        b["files"] = [f.name for f in files[:5]]
    modules["b"] = b

    # --- Module D: k6 scripts and results ---
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
    modules["d"] = d

    return modules


# ---------------------------------------------------------------------------
# One full snapshot
# ---------------------------------------------------------------------------
def collect(probe_enabled=True):
    """Gather one complete snapshot of the demo for the dashboard."""
    docker_state = read_docker_state()
    nginx = read_nginx_upstream()
    actions = read_scale_actions()

    ready = [r for r in docker_state["replicas"] if r["ready"]]
    # A replica Docker says is healthy but nginx is not routing to means the
    # controller has not run since it appeared -- worth showing, since it is
    # exactly the drift the controller exists to prevent.
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
        "prediction": read_prediction(),
        "probe": probe_portal(probe_enabled),
        "probe_summary": probe_summary(),
        "modules": read_other_modules(),
        "paths": {
            "repo_root": str(REPO_ROOT),
            "module_c": str(MODULE_C_DIR),
            "entrypoint": PORTAL_ENTRYPOINT,
        },
    }
