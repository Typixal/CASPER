"""Latency probe: the reactive baseline's only view of the system."""

import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field


def percentile(samples, pct):
    """Nearest-rank percentile.

    Nearest-rank always returns an observed value; interpolating a handful of
    probe samples would report a latency nobody saw.

    Args:
        samples: Numbers to rank.
        pct: Percentile, e.g. 95.

    Returns:
        The sample at that rank.

    Raises:
        ValueError: If samples is empty.
    """
    if not samples:
        raise ValueError("cannot take a percentile of zero samples")

    ordered = sorted(samples)
    rank = math.ceil(pct / 100.0 * len(ordered))
    return ordered[max(rank, 1) - 1]


@dataclass
class ProbeResult:
    """One probe round.

    Attributes:
        latencies_ms: One latency per request; failures count as the timeout.
        errors: Number of failed requests.
    """

    latencies_ms: list = field(default_factory=list)
    errors: int = 0


def _one_request(url, timeout_s):
    """Send one GET.

    Returns:
        (latency_ms, ok). A failure is scored at the full timeout: a fast 503
        recorded at face value would make an overloaded portal look quick.
    """
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            response.read()
            ok = 200 <= response.status < 300
    except (urllib.error.URLError, OSError):
        # Covers HTTPError (e.g. 503) and refused connections.
        ok = False

    if not ok:
        return timeout_s * 1000.0, False
    return (time.perf_counter() - started) * 1000.0, True


def measure(url, requests=8, timeout_s=3.0):
    """Send concurrent GETs and report latencies and errors.

    Concurrent so the probe sees the queueing a saturated replica causes.

    Args:
        url: Target, normally the nginx entrypoint.
        requests: Number of concurrent requests.
        timeout_s: Per-request timeout.

    Returns:
        A ProbeResult.
    """
    with ThreadPoolExecutor(max_workers=requests) as pool:
        outcomes = list(pool.map(lambda _: _one_request(url, timeout_s), range(requests)))

    return ProbeResult(
        latencies_ms=[latency for latency, _ in outcomes],
        errors=sum(1 for _, ok in outcomes if not ok),
    )
