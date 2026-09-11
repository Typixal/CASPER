"""
CASPER demo portal (Module C).

Stands in for a government exam-result portal. There is no real business
logic here on purpose -- the only job of this app is to be something we can
put under load and scale horizontally, so Module D's k6 test has a realistic
target.

Every response reports which container served it (the HOSTNAME env var, which
Docker sets to the container ID). That is how we prove nginx is actually
load-balancing across the replicas the scale controller created.
"""

import os
import random
import socket
import time

from flask import Flask, jsonify

app = Flask(__name__)

# Artificial "database lookup + render" delay, in milliseconds.
# Tunable from docker-compose.yml so the team can make the portal slower or
# faster without rebuilding the image.
MIN_DELAY_MS = int(os.environ.get("MIN_DELAY_MS", "20"))
MAX_DELAY_MS = int(os.environ.get("MAX_DELAY_MS", "120"))

# Docker sets HOSTNAME to the container ID. Fall back to the real hostname
# when running the app directly on a laptop (outside Docker).
REPLICA_ID = os.environ.get("HOSTNAME") or socket.gethostname()


def simulate_work():
    """Sleep for a random delay to imitate a DB lookup and page render."""
    delay_ms = random.randint(MIN_DELAY_MS, MAX_DELAY_MS)
    time.sleep(delay_ms / 1000.0)
    return delay_ms


@app.route("/")
def index():
    """Basic status/info response."""
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
    """
    The endpoint Module D's k6 load test hammers.

    Includes an artificial delay so that an under-provisioned stack shows up
    as rising response times, exactly like a real overloaded portal would.
    """
    delay_ms = simulate_work()
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
    """
    Plain health check.

    Used by the Docker healthcheck, and indirectly by the scale controller:
    the controller only adds a replica to nginx once Docker reports it healthy.
    No artificial delay here -- a health check must stay fast.
    """
    return jsonify({"status": "healthy", "served_by": REPLICA_ID}), 200


if __name__ == "__main__":
    # 0.0.0.0 is required: binding to localhost would make the port
    # unreachable from nginx in the other container.
    app.run(host="0.0.0.0", port=5000)
