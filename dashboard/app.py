"""Live demo dashboard: Flask backend serving snapshots over SSE.

Read-only: it observes Docker state, nginx.conf, the audit log and the
Prediction files, and never scales anything. Runs on the host as its own
process.

Usage:
    python app.py    # http://localhost:8050

Environment:
    CASPER_DASH_REFRESH       snapshot interval, seconds (default 2)
    CASPER_DASH_PORT          port (default 8050)
    CASPER_DASH_PROBE         "0" starts with the latency probe off
    CASPER_DASH_PROBE_LOCKED  "1" keeps the probe off; the toggle returns 409
"""

import json
import os
import re
import threading
import time

from flask import Flask, Response, abort, jsonify, render_template, send_from_directory

import collector

app = Flask(__name__)

REFRESH_SECONDS = float(os.environ.get("CASPER_DASH_REFRESH", "2"))
PORT = int(os.environ.get("CASPER_DASH_PORT", "8050"))

# The probe adds one request per refresh, so it must be off during a k6 run.
_probe_enabled = os.environ.get("CASPER_DASH_PROBE", "1") != "0"

# Set by run-demo.ps1 -Compare so a stray click cannot re-enable the probe mid-run.
_probe_locked = os.environ.get("CASPER_DASH_PROBE_LOCKED", "0") == "1"


def probe_enabled():
    """Whether the latency probe is on."""
    return _probe_enabled


def probe_locked():
    """Whether the probe toggle is locked off."""
    return _probe_locked

_state = {"generated_at": None, "starting": True}
_state_lock = threading.Lock()


def _collect_loop():
    """Refresh the shared snapshot every REFRESH_SECONDS, forever."""
    global _state
    while True:
        try:
            snapshot = collector.collect(probe_enabled=_probe_enabled)
            snapshot["probe"]["locked"] = _probe_locked
        except Exception as exc:  # keep the dashboard alive whatever happens
            snapshot = {
                "generated_at": None,
                "fatal_error": "{}: {}".format(type(exc).__name__, exc),
            }
        with _state_lock:
            _state = snapshot
        time.sleep(REFRESH_SECONDS)


def _current_state():
    """Return the latest snapshot."""
    with _state_lock:
        return _state


@app.route("/")
def index():
    """Serve the built React app."""
    return render_template("index.html", refresh_seconds=REFRESH_SECONDS)


@app.route("/api/state")
def api_state():
    """Return the current snapshot as JSON."""
    return jsonify(_current_state())


@app.route("/api/probe/toggle", methods=["POST"])
def api_probe_toggle():
    """Flip the latency probe on or off.

    Returns:
        The new state, or 409 if the probe is locked.
    """
    global _probe_enabled
    if _probe_locked:
        return jsonify({"probe_enabled": _probe_enabled, "locked": True}), 409
    _probe_enabled = not _probe_enabled
    return jsonify({"probe_enabled": _probe_enabled})


_CHART_NAME = re.compile(r"^[A-Za-z0-9_\-]+\.png$")


@app.route("/api/results/<path:name>")
def api_result_chart(name):
    """Serve one of Module D's chart PNGs.

    Only bare *.png names from the results folder; anything else is a 404.
    """
    if not _CHART_NAME.match(name):
        abort(404)
    return send_from_directory(collector.MODULE_D_RESULTS_DIR, name, mimetype="image/png")


@app.route("/stream")
def stream():
    """Push each new snapshot to the browser as a server-sent event."""

    def event_stream():
        last_sent = None
        while True:
            snapshot = _current_state()
            stamp = snapshot.get("generated_at")
            if stamp != last_sent:
                last_sent = stamp
                yield "data: {}\n\n".format(json.dumps(snapshot))
            time.sleep(0.4)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering
        },
    )


if __name__ == "__main__":
    threading.Thread(target=_collect_loop, daemon=True).start()
    print("CASPER dashboard -> http://localhost:{}".format(PORT))
    print("Watching: {}".format(collector.MODULE_C_DIR))
    # The reloader would start a second collector thread.
    app.run(host="127.0.0.1", port=PORT, threaded=True, use_reloader=False)
