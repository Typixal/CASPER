"""Exam-result-day traffic curve shared by both comparison runs.

quiet -> sharp ramp -> sustained peak -> decay, compressed to a few minutes
and sized for a laptop (~4 replicas at the default peak).
"""

import json
import math
from pathlib import Path

QUIET_S = 45
RAMP_S = 20
PEAK_S = 90
DECAY_S = 45

RAMP_START_S = QUIET_S
TOTAL_S = QUIET_S + RAMP_S + PEAK_S + DECAY_S

QUIET_FRACTION = 0.05  # quiet load as a share of peak
DECAY_FRACTION = 0.10  # load at the end of the decay as a share of peak


def k6_config(peak_rps):
    """Build k6 ramping-arrival-rate settings for the curve.

    Args:
        peak_rps: Requests per second at the peak.

    Returns:
        Dict with startRate and stages, as read by k6/exam_day_traffic.js.
    """
    quiet = max(1, round(peak_rps * QUIET_FRACTION))
    tail = max(1, round(peak_rps * DECAY_FRACTION))
    return {
        "startRate": quiet,
        "stages": [
            {"target": quiet, "duration": "{}s".format(QUIET_S)},
            {"target": peak_rps, "duration": "{}s".format(RAMP_S)},
            {"target": peak_rps, "duration": "{}s".format(PEAK_S)},
            {"target": tail, "duration": "{}s".format(DECAY_S)},
        ],
    }


def write_k6_config(path, peak_rps):
    """Write k6_config() as JSON.

    Args:
        path: Output file; parent folders are created.
        peak_rps: Requests per second at the peak.

    Returns:
        The path written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(k6_config(peak_rps), indent=2), encoding="utf-8")
    return path


def replicas_needed(peak_rps, per_replica_rps):
    """Replicas to serve peak_rps, rounded up (Module B's rule).

    Args:
        peak_rps: Demand in requests per second.
        per_replica_rps: Capacity of one replica.

    Returns:
        At least 1.
    """
    return max(1, math.ceil(peak_rps / per_replica_rps))
