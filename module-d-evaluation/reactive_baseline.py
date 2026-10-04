"""Reactive baseline: a conventional latency-driven auto-scaler.

Scales up after sustained p95 breaches and down after sustained calm, with a
cooldown. The guards are standard practice, not a handicap; its only real
weakness is that it reacts to load that has already arrived.

Usage:
    python reactive_baseline.py [--max 6] [--interval 5] ...
"""


class ReactiveScaler:
    """Pure scaling decision logic; the caller supplies the clock.

    Args:
        min_replicas: Lower bound.
        max_replicas: Upper bound.
        up_threshold_ms: p95 above this is a breach.
        down_threshold_ms: p95 below this is calm.
        up_after: Consecutive breaches before scaling up.
        down_after: Consecutive calm ticks before scaling down.
        step_up: Replicas added per scale-up.
        step_down: Replicas removed per scale-down.
        cooldown_s: Minimum seconds between scale actions.
    """

    def __init__(
        self,
        min_replicas=1,
        max_replicas=6,
        up_threshold_ms=400,
        down_threshold_ms=150,
        up_after=2,
        down_after=6,
        step_up=2,
        step_down=1,
        cooldown_s=15,
    ):
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.up_threshold_ms = up_threshold_ms
        self.down_threshold_ms = down_threshold_ms
        self.up_after = up_after
        self.down_after = down_after
        self.step_up = step_up
        self.step_down = step_down
        self.cooldown_s = cooldown_s

        self._breaches = 0
        self._calm = 0
        self._last_scaled_at = None

    def decide(self, p95_ms, current, now):
        """Choose the replica count for this tick.

        Args:
            p95_ms: Latest measured p95 latency.
            current: Replicas running now.
            now: Monotonic time in seconds.

        Returns:
            Target replica count (== current when no action is taken).
        """
        if p95_ms > self.up_threshold_ms:
            self._breaches += 1
            self._calm = 0
        elif p95_ms < self.down_threshold_ms:
            self._calm += 1
            self._breaches = 0
        else:
            # Between thresholds: neither streak survives.
            self._breaches = 0
            self._calm = 0

        if self._cooling_down(now):
            return current

        target = current
        if self._breaches >= self.up_after:
            target = min(current + self.step_up, self.max_replicas)
        elif self._calm >= self.down_after:
            target = max(current - self.step_down, self.min_replicas)

        if target != current:
            self._last_scaled_at = now
            self._breaches = 0
            self._calm = 0
        return target

    def _cooling_down(self, now):
        """True while within cooldown_s of the last scale action."""
        return (
            self._last_scaled_at is not None
            and now - self._last_scaled_at < self.cooldown_s
        )


def run_loop(scaler, read_p95, scale, current, interval_s, should_stop, now, sleep):
    """Probe, decide and scale until should_stop() is true.

    Side effects are injected so the loop is testable without Docker.

    Args:
        scaler: A ReactiveScaler.
        read_p95: Returns the current p95 in ms.
        scale: Scales to n and returns the replicas actually healthy.
        current: Starting replica count.
        interval_s: Seconds between ticks.
        should_stop: Returns True to end the loop.
        now: Clock returning seconds.
        sleep: Sleeps for the given seconds.

    Returns:
        The final replica count.
    """
    while not should_stop():
        p95 = read_p95()
        target = scaler.decide(p95, current=current, now=now())
        if target != current:
            # Continue from what actually came up, not from what was asked for.
            current = scale(target)
        sleep(interval_s)
    return current


def parse_args(argv):
    """Parse command-line arguments."""
    import argparse

    parser = argparse.ArgumentParser(description="CASPER reactive baseline auto-scaler")
    parser.add_argument("--url", default="http://localhost:8080/results",
                        help="what to probe -- the nginx entrypoint, never a portal container")
    parser.add_argument("--interval", type=float, default=5, help="seconds between probes")
    parser.add_argument("--probes", type=int, default=8, help="concurrent requests per probe")
    parser.add_argument("--min", type=int, default=1)
    parser.add_argument("--max", type=int, default=6)
    parser.add_argument("--up-ms", type=float, default=400, help="p95 that counts as a breach")
    parser.add_argument("--down-ms", type=float, default=150, help="p95 that counts as calm")
    return parser.parse_args(argv)


def scaler_from_args(args):
    """Build a ReactiveScaler from parsed arguments."""
    return ReactiveScaler(
        min_replicas=args.min,
        max_replicas=args.max,
        up_threshold_ms=args.up_ms,
        down_threshold_ms=args.down_ms,
    )


def main(argv=None):
    """Probe nginx and scale through Module C (source="reactive") until stopped.

    Needs Docker, so it is not unit-tested; its decisions go through the
    tested run_loop and ReactiveScaler.
    """
    import sys
    import time

    import module_c
    import probe

    args = parse_args(sys.argv[1:] if argv is None else argv)
    controller = module_c.controller()
    scaler = scaler_from_args(args)

    def read_p95():
        result = probe.measure(args.url, requests=args.probes)
        p95 = probe.percentile(result.latencies_ms, 95)
        print("[reactive] p95={:.0f}ms errors={}/{}".format(p95, result.errors, args.probes), flush=True)
        return p95

    def scale(n):
        print("[reactive] scaling to {}".format(n), flush=True)
        return len(controller.scale_to(n, source="reactive"))

    current = controller.current_replica_count()
    print("[reactive] starting at {} replica(s), probing {}".format(current, args.url), flush=True)
    try:
        run_loop(scaler, read_p95, scale, current, args.interval,
                 should_stop=lambda: False, now=time.monotonic, sleep=time.sleep)
    except KeyboardInterrupt:
        print("[reactive] stopped", flush=True)


if __name__ == "__main__":
    main()
