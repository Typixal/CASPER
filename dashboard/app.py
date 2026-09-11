"""
CASPER live demo dashboard.

A small Flask app that shows, on one screen, what the CASPER demo is doing
right now: how many portal replicas exist, which of them nginx is routing to,
what the predictive policy has planned, and every scaling action as it lands
in the audit log.

    python dashboard/app.py        ->  http://localhost:8050

It is READ-ONLY by design. It observes the demo through the artifacts the
system already writes (Docker state, nginx.conf, scale_actions.jsonl,
the Prediction file) and never scales anything itself. Running it, or closing
it, cannot affect a demo in progress.

It runs on the host as its own process -- docker-compose.yml is untouched, so
the tested Module C stack behaves exactly as before.
"""

import json
import os
import threading
import time

from flask import Flask, Response, jsonify, render_template

import collector

app = Flask(__name__)

# How often the background thread takes a fresh snapshot, in seconds.
REFRESH_SECONDS = float(os.environ.get("CASPER_DASH_REFRESH", "2"))
PORT = int(os.environ.get("CASPER_DASH_PORT", "8050"))

# The probe sends one request per refresh to localhost:8080 to measure live
# latency. Turn it off (from the UI, or with CASPER_DASH_PROBE=0) before a
# Module D load test so it adds no traffic to the measured run.
_probe_enabled = os.environ.get("CASPER_DASH_PROBE", "1") != "0"

_state = {"generated_at": None, "starting": True}
_state_lock = threading.Lock()


def _collect_loop():
    """Background thread: refresh the snapshot on a fixed interval."""
    global _state
    while True:
        try:
            snapshot = collector.collect(probe_enabled=_probe_enabled)
        except Exception as exc:  # keep the dashboard alive whatever happens
            snapshot = {
                "generated_at": None,
                "fatal_error": "{}: {}".format(type(exc).__name__, exc),
            }
        with _state_lock:
            _state = snapshot
        time.sleep(REFRESH_SECONDS)


def _current_state():
    with _state_lock:
        return _state


@app.route("/")
def index():
    return render_template("index.html", refresh_seconds=REFRESH_SECONDS)


@app.route("/api/state")
def api_state():
    """Current snapshot as JSON. Handy for debugging, or for a second screen."""
    return jsonify(_current_state())


@app.route("/api/probe/toggle", methods=["POST"])
def api_probe_toggle():
    """Turn the dashboard's own latency probe on or off."""
    global _probe_enabled
    _probe_enabled = not _probe_enabled
    return jsonify({"probe_enabled": _probe_enabled})


@app.route("/stream")
def stream():
    """
    Server-sent events: push a snapshot to the browser as each one is taken.

    SSE rather than polling so the page updates the moment a scaling action
    lands -- which matters when demonstrating that CASPER scaled *before* the
    traffic arrived.
    """

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
            "X-Accel-Buffering": "no",  # in case this ever sits behind a proxy
        },
    )


if __name__ == "__main__":
    threading.Thread(target=_collect_loop, daemon=True).start()
    print("CASPER dashboard -> http://localhost:{}".format(PORT))
    print("Watching: {}".format(collector.MODULE_C_DIR))
    # use_reloader=False: the reloader would start a second collector thread.
    app.run(host="127.0.0.1", port=PORT, threaded=True, use_reloader=False)
