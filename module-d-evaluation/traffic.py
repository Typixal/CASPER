"""Module D -- the exam-result-day traffic curve.

Both runs (reactive and predictive) replay exactly this curve, so the only
thing that differs between them is which brain is turning the scaling knob.

Shape, as documented for the project: quiet -> sharp ramp -> sustained peak
-> decay. It is compressed into a few minutes so the experiment fits a demo,
and sized for a laptop: the peak needs ~4 replicas, not the 12-20 the full
Module B estimates call for.
"""

import json
import math
from pathlib import Path

# Segment lengths, in seconds.
QUIET_S = 45   # candidates idling before publication
RAMP_S = 20    # result goes live: a sharp climb
PEAK_S = 90    # sustained peak
DECAY_S = 45   # tailing off

RAMP_START_S = QUIET_S
TOTAL_S = QUIET_S + RAMP_S + PEAK_S + DECAY_S

QUIET_FRACTION = 0.05  # quiet-period load, as a share of peak
DECAY_FRACTION = 0.10  # where the decay ends, as a share of peak


def k6_config(peak_rps):
    """The curve as k6 ramping-arrival-rate settings: startRate + stages.

    Arrival rate is the right executor for this experiment: it keeps sending
    requests at the scheduled rate whether or not the portal keeps up -- like
    real candidates hitting refresh -- so under-provisioning shows up as
    latency and errors, rather than as a load generator politely slowing down.
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
    """Write the curve to `path` for the k6 script to read. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(k6_config(peak_rps), indent=2), encoding="utf-8")
    return path


def replicas_needed(peak_rps, per_replica_rps):
    """Replicas to serve `peak_rps`, by the same rule Module B uses.

    Demand divided by per-replica capacity, always rounded up: a fractional
    replica cannot run, and rounding down is under-provisioning.
    """
    return max(1, math.ceil(peak_rps / per_replica_rps))
