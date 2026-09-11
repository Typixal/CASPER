"""
CASPER shared scale controller (Module C).

This is the single piece of real infrastructure logic in the project: the
"knob" that changes how much capacity is running. Both scaling brains turn
this same knob --

    * the predictive policy  (Module C, policy/predictive_policy.py)
    * the reactive baseline  (Module D, imports scale_to from this file)

Every scaling action is appended to logs/scale_actions.jsonl with a `source`
tag, so afterwards we can tell exactly which strategy did what, and when.

Direct smoke test (no policy, no prediction involved):

    python controller/scale_controller.py 3

IMPORTANT for Module D: importing this file must be side-effect free. Nothing
below runs Docker at import time -- only inside functions and under the
__main__ guard.
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths. Everything is resolved relative to the project root (the folder that
# holds docker-compose.yml), so the script works no matter which directory the
# team runs it from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
NGINX_TEMPLATE = PROJECT_ROOT / "nginx" / "nginx.conf.template"
NGINX_CONF = PROJECT_ROOT / "nginx" / "nginx.conf"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "scale_actions.jsonl"

# Markers in nginx.conf.template. Everything between them is replaced with the
# current healthy replica list.
BEGIN_MARKER = "# --- BEGIN AUTO-GENERATED SERVERS ---"
END_MARKER = "# --- END AUTO-GENERATED SERVERS ---"

# nginx refuses to start with an empty upstream block, so a fully drained
# stack (n == 0) is represented by a single server that is marked down.
EMPTY_UPSTREAM_LINE = "        server 127.0.0.1:1 down;"

# The port the Flask portal listens on inside the container.
PORTAL_PORT = 5000

# After scaling up, containers need a moment to boot and pass their first
# healthcheck. We poll Docker until the expected number are healthy, or until
# this many seconds have passed (whichever comes first).
HEALTH_POLL_TIMEOUT_SECONDS = 45
HEALTH_POLL_INTERVAL_SECONDS = 2


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------
def _compose(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """
    Run a `docker compose ...` command from the project root.

    Raises subprocess.CalledProcessError if the command fails, so a broken
    Docker setup surfaces loudly instead of silently producing a wrong
    nginx config.
    """
    cmd = ["docker", "compose", *args]
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )


def _parse_compose_ps(raw: str) -> list:
    """
    Parse the output of `docker compose ps --format json`.

    Different Compose versions print either one JSON object per line or a
    single JSON array, so handle both rather than betting on one.
    """
    raw = raw.strip()
    if not raw:
        return []

    # Array form.
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    # Line-delimited form.
    containers = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            # Ignore any non-JSON noise Compose may print.
            continue
    return containers


def _healthy_replica_names() -> list:
    """
    Ask Docker which portal containers are actually usable right now.

    A replica counts as usable when it is running AND either reports healthy
    or reports no health status at all (an image without a healthcheck).
    A container that is still "starting" is deliberately excluded -- nginx
    must never be told to route to a replica Docker has not confirmed.
    """
    result = _compose("ps", "portal", "--format", "json", capture=True)
    containers = _parse_compose_ps(result.stdout)

    names = []
    for container in containers:
        state = str(container.get("State", "")).lower()
        health = str(container.get("Health", "")).lower()
        if state == "running" and health in ("healthy", "", "none"):
            name = container.get("Name") or container.get("Names")
            if name:
                names.append(name)

    # Sort for a stable, readable nginx.conf diff between runs.
    return sorted(names)


def _wait_for_healthy(expected: int, settle_seconds: float) -> list:
    """
    Give containers time to come up, then poll until `expected` replicas are
    healthy (or the timeout expires).

    Returns whatever is genuinely healthy at the end -- which may be fewer
    than expected if a container failed to start. That is the honest answer
    and is exactly what nginx should be configured with.
    """
    if expected <= 0:
        return _healthy_replica_names()

    time.sleep(settle_seconds)

    deadline = time.monotonic() + HEALTH_POLL_TIMEOUT_SECONDS
    names = _healthy_replica_names()
    while len(names) < expected and time.monotonic() < deadline:
        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
        names = _healthy_replica_names()

    if len(names) < expected:
        print(
            "[controller] WARNING: asked for {} replicas but only {} are "
            "healthy. nginx will be configured with the {} that actually "
            "work.".format(expected, len(names), len(names))
        )
    return names


# ---------------------------------------------------------------------------
# nginx config generation
# ---------------------------------------------------------------------------
def _render_nginx_conf(replica_names: list) -> str:
    """Build the nginx config text for the given replica list."""
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")

    if replica_names:
        server_lines = "\n".join(
            "        server {}:{};".format(name, PORTAL_PORT)
            for name in replica_names
        )
    else:
        server_lines = EMPTY_UPSTREAM_LINE

    replacement = "{}\n{}\n{}".format(BEGIN_MARKER, server_lines, END_MARKER)

    pattern = re.compile(
        re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    new_conf, count = pattern.subn(replacement, template)
    if count != 1:
        raise RuntimeError(
            "Expected exactly one auto-generated block in {}, found {}. "
            "Did the markers get edited?".format(NGINX_TEMPLATE, count)
        )
    return new_conf


def _write_nginx_conf(replica_names: list) -> None:
    """Write the generated config to nginx/nginx.conf."""
    NGINX_CONF.write_text(_render_nginx_conf(replica_names), encoding="utf-8")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def _log_action(requested: int, replica_names: list, source: str) -> None:
    """
    Append one JSON line describing what just happened.

    This file is the "executed action" half of Module C's required
    predicted-event -> planned-action -> executed-action trail, and it is what
    Module D reads to compare the two strategies.
    """
    LOG_DIR.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "scale_to",
        "requested_replicas": requested,
        "actual_healthy_replicas": len(replica_names),
        "replica_names": replica_names,
        "source": source,
    }
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def scale_to(n: int, source: str = "manual", settle_seconds: float = 3.0) -> list:
    """
    Scale the portal to exactly n replicas, update nginx to match, log the action.

    Args:
        n: target replica count (0 means fully drained).
        source: who asked for this -- "predictive", "reactive", or "manual".
                Module D's comparison depends on this being set correctly.
        settle_seconds: initial pause before checking health, giving Flask
                time to boot.

    Returns:
        The list of replica container names nginx was actually pointed at.
    """
    if n < 0:
        raise ValueError("Replica count cannot be negative.")

    print("[controller] scaling portal to {} replica(s) (source={})".format(n, source))

    # 1. Ask Docker for the new replica count.
    #    --no-deps + naming only `portal` keeps this call from touching nginx:
    #    nginx must not be (re)started until step 4 has written a config that
    #    matches the replicas that actually exist.
    _compose("up", "-d", "--no-deps", "--scale", "portal={}".format(n), "portal")

    # 2 & 3. Wait, then re-derive the REAL healthy list from Docker.
    #        Never trust the requested N blindly -- a container may have
    #        failed to start, and nginx must not route to it.
    replica_names = _wait_for_healthy(n, settle_seconds)
    print("[controller] healthy replicas: {}".format(replica_names or "(none)"))

    # 4. Regenerate the nginx config to match reality.
    _write_nginx_conf(replica_names)

    # 5. Make sure nginx exists before trying to exec into it. Harmless and
    #    idempotent if it is already running; necessary on the very first
    #    call against a fresh stack.
    #
    #    --no-deps is essential here, not cosmetic: without it Compose would
    #    also bring up nginx's `depends_on` target (portal) at its DEFAULT
    #    scale of 1, silently destroying the replicas we just created.
    _compose("up", "-d", "--no-deps", "nginx")

    # 6. Zero-downtime reload -- NOT a restart. In-flight requests finish on
    #    the old config while new ones use the new one. This is what makes
    #    scaling down a graceful drain rather than a kill.
    _compose("exec", "-T", "nginx", "nginx", "-s", "reload")

    # 7. Audit trail.
    _log_action(n, replica_names, source)

    return replica_names


def current_replica_count() -> int:
    """Return how many healthy replicas are live right now."""
    return len(_healthy_replica_names())


# ---------------------------------------------------------------------------
# Manual smoke test:  python controller/scale_controller.py 3
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python controller/scale_controller.py <replica_count>")
        print("Example: python controller/scale_controller.py 3")
        sys.exit(1)

    try:
        target = int(sys.argv[1])
    except ValueError:
        print("'{}' is not a whole number.".format(sys.argv[1]))
        sys.exit(1)

    names = scale_to(target, source="manual")
    print(
        "[controller] done. {} replica(s) behind nginx on "
        "http://localhost:8080".format(len(names))
    )
