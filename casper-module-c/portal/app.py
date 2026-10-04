"""Demo exam-result portal: the load-test target that Module C scales.

No business logic. Each response names the container that served it
(HOSTNAME is the container ID), which shows nginx balancing across replicas.
"""

import os
import random
import socket
import threading
import time

from flask import Flask, jsonify

app = Flask(__name__)

# Simulated lookup + render time per /results request.
MIN_DELAY_MS = int(os.environ.get("MIN_DELAY_MS", "20"))
MAX_DELAY_MS = int(os.environ.get("MAX_DELAY_MS", "120"))

# Per-replica capacity: queue up to QUEUE_TIMEOUT_MS, then 503. Without it,
# load barely moves latency and the reactive scaler has nothing to react to.
# 5 slots at ~70 ms is ~4200 req/min, matching the ~4000 req/min basis.
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "5"))
QUEUE_TIMEOUT_MS = int(os.environ.get("QUEUE_TIMEOUT_MS", "2000"))
_capacity = threading.BoundedSemaphore(MAX_CONCURRENT)

REPLICA_ID = os.environ.get("HOSTNAME") or socket.gethostname()


def simulate_work():
    """Sleep a random delay to imitate a lookup and render.

    Returns:
        The delay in milliseconds.
    """
    delay_ms = random.randint(MIN_DELAY_MS, MAX_DELAY_MS)
    time.sleep(delay_ms / 1000.0)
    return delay_ms


@app.route("/")
def index():
    """Service info."""
    return jsonify(
        {
            "service": "casper-demo-portal",
            "status": "ok",
            "served_by": REPLICA_ID,
            "endpoints": ["/", "/results", "/health"],
        }
    )


@app.route("/results")
def results():
    """Load-test endpoint: simulated work behind the capacity gate.

    Returns:
        200 with a fake result, or 503 when no slot frees within the timeout.
    """
    if not _capacity.acquire(timeout=QUEUE_TIMEOUT_MS / 1000.0):
        return jsonify({"error": "replica at capacity", "served_by": REPLICA_ID}), 503
    try:
        delay_ms = simulate_work()
    finally:
        _capacity.release()

    return jsonify(
        {
            "event": "exam_result",
            "result": "PASS",
            "candidate_ref": random.randint(100000, 999999),
            "simulated_delay_ms": delay_ms,
            "served_by": REPLICA_ID,
        }
    )


@app.route("/health")
def health():
    """Docker healthcheck.

    Deliberately not gated: a busy replica is still healthy, and failing here
    would pull saturated replicas out of nginx mid-spike.
    """
    return jsonify({"status": "healthy", "served_by": REPLICA_ID}), 200


if __name__ == "__main__":
    # 0.0.0.0 so nginx in another container can reach it.
    app.run(host="0.0.0.0", port=5000)
