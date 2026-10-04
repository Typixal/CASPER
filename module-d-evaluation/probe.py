"""Module D -- latency probe for the reactive baseline.

The reactive scaler is an honest stand-in for a conventional latency-driven
auto-scaler: it only knows what it can measure right now, by sending a few
requests through nginx and looking at how long they took.
"""

import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field


def percentile(samples, pct):
    """Nearest-rank percentile of `samples` (e.g. pct=95 for p95).

    Nearest-rank always returns a value that was actually observed, which is
    the honest thing to report for a small probe round of a handful of
    requests -- interpolating would invent a latency nobody experienced.
    """
    if not samples:
        raise ValueError("cannot take a percentile of zero samples")

    ordered = sorted(samples)
    rank = math.ceil(pct / 100.0 * len(ordered))
    return ordered[max(rank, 1) - 1]


@dataclass
class ProbeResult:
    """One probe round: a latency per request, and how many failed."""

    latencies_ms: list = field(default_factory=list)
    errors: int = 0


def _one_request(url, timeout_s):
    """Return (latency_ms, ok) for a single GET."""
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            response.read()
            ok = 200 <= response.status < 300
    except (urllib.error.URLError, OSError):
        # HTTPError (e.g. 503) is a URLError subclass; so is connection
        # refused. Both mean the user did not get their result.
        ok = False

    if not ok:
        # Score a failure at the full timeout. A refused request comes back
        # fast; recording that would make an overloaded portal look quick.
        return timeout_s * 1000.0, False
    return (time.perf_counter() - started) * 1000.0, True


def measure(url, requests=8, timeout_s=3.0):
    """Send `requests` concurrent GETs to `url` and report what happened.

    Concurrent, not sequential: a reactive scaler polling once every few
    seconds sees a burst of real traffic, and one slow request at a time would
    under-report the queueing a saturated replica causes.
    """
    with ThreadPoolExecutor(max_workers=requests) as pool:
        outcomes = list(pool.map(lambda _: _one_request(url, timeout_s), range(requests)))

    return ProbeResult(
        latencies_ms=[latency for latency, _ in outcomes],
        errors=sum(1 for _, ok in outcomes if not ok),
    )
