"""Shared scale controller: the one knob both scaling strategies turn.

Scales the portal with Docker Compose, rewrites nginx's upstream to the
replicas that are actually healthy, reloads nginx, and appends every action to
logs/scale_actions.jsonl tagged with its `source`.

Import-safe: nothing touches Docker at import time (Module D imports
`scale_to` from here).

Usage:
    python controller/scale_controller.py <replica_count>
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NGINX_TEMPLATE = PROJECT_ROOT / "nginx" / "nginx.conf.template"
NGINX_CONF = PROJECT_ROOT / "nginx" / "nginx.conf"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "scale_actions.jsonl"

# The template block between these markers is replaced with the replica list.
BEGIN_MARKER = "# --- BEGIN AUTO-GENERATED SERVERS ---"
END_MARKER = "# --- END AUTO-GENERATED SERVERS ---"

# nginx rejects an empty upstream, so a drained stack gets one dead server.
EMPTY_UPSTREAM_LINE = "        server 127.0.0.1:1 down;"

PORTAL_PORT = 5000

HEALTH_POLL_TIMEOUT_SECONDS = 45
HEALTH_POLL_INTERVAL_SECONDS = 2


def _compose(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """Run `docker compose <args>` from the project root.

    Args:
        *args: Arguments after `docker compose`.
        capture: Capture stdout/stderr instead of streaming them.

    Returns:
        The completed process.

    Raises:
        subprocess.CalledProcessError: If the command exits non-zero.
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
    """Parse `docker compose ps --format json` output.

    Compose versions differ: some print a JSON array, others one object per
    line. Both are accepted; non-JSON lines are skipped.

    Args:
        raw: The command's stdout.

    Returns:
        One dict per container.
    """
    raw = raw.strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    containers = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return containers


def _healthy_replica_names() -> list:
    """List portal containers that are safe to route to.

    A replica qualifies when it is running and healthy, or has no healthcheck.
    "starting" is excluded: nginx must never route to an unconfirmed replica.

    Returns:
        Container names, sorted so nginx.conf diffs stay stable.
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

    return sorted(names)


def _wait_for_healthy(expected: int, settle_seconds: float) -> list:
    """Wait until `expected` replicas are healthy or the poll times out.

    Args:
        expected: Replica count to wait for.
        settle_seconds: Initial pause before the first health check.

    Returns:
        The replicas healthy at the end, possibly fewer than expected if a
        container failed to start.
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


def _render_nginx_conf(replica_names: list) -> str:
    """Render nginx.conf from the template for the given replicas.

    Args:
        replica_names: Container names to put in the upstream block.

    Returns:
        The full config text.

    Raises:
        RuntimeError: If the template does not contain exactly one marker block.
    """
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
    """Write the rendered config to nginx/nginx.conf."""
    NGINX_CONF.write_text(_render_nginx_conf(replica_names), encoding="utf-8")


def _log_action(requested: int, replica_names: list, source: str) -> None:
    """Append one scale action to the JSONL audit log Module D reads.

    Args:
        requested: Replica count that was asked for.
        replica_names: Replicas actually routed afterwards.
        source: "predictive", "reactive" or "manual".
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


def scale_to(n: int, source: str = "manual", settle_seconds: float = 3.0) -> list:
    """Scale the portal to n replicas, point nginx at the healthy ones, log it.

    Args:
        n: Target replica count; 0 drains the stack.
        source: Who asked: "predictive", "reactive" or "manual". Module D
            separates the two strategies by this tag.
        settle_seconds: Pause before the first health check.

    Returns:
        Container names nginx now routes to.

    Raises:
        ValueError: If n is negative.
        subprocess.CalledProcessError: If a Compose command fails.
    """
    if n < 0:
        raise ValueError("Replica count cannot be negative.")

    print("[controller] scaling portal to {} replica(s) (source={})".format(n, source))

    # --no-deps and naming only `portal`: nginx must not restart until its
    # config matches the replicas that exist.
    _compose("up", "-d", "--no-deps", "--scale", "portal={}".format(n), "portal")

    # Route only to what Docker confirms, never to the requested n.
    replica_names = _wait_for_healthy(n, settle_seconds)
    print("[controller] healthy replicas: {}".format(replica_names or "(none)"))

    _write_nginx_conf(replica_names)

    # Ensures nginx exists on a fresh stack. --no-deps is required: without it
    # Compose also starts nginx's depends_on (portal) at scale 1, destroying
    # the replicas just created.
    _compose("up", "-d", "--no-deps", "nginx")

    # Reload, not restart: in-flight requests finish, so scale-down drains.
    _compose("exec", "-T", "nginx", "nginx", "-s", "reload")

    _log_action(n, replica_names, source)

    return replica_names


def current_replica_count() -> int:
    """Return the number of healthy replicas right now."""
    return len(_healthy_replica_names())


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
