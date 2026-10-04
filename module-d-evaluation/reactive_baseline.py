"""Module D -- the reactive baseline auto-scaler.

The thing CASPER has to beat. It behaves the way a conventional latency-driven
auto-scaler does: poll a live metric, scale up after a sustained breach, scale
down after a sustained quiet period, with a cooldown so it does not thrash.

It must stay an HONEST baseline. Every guard here (consecutive-breach
requirement, cooldown, min/max) is standard practice in real auto-scalers,
not a handicap added to make CASPER look good. Its one real limitation is the
one the project is about: it can only react to load that has already arrived.
"""


class ReactiveScaler:
    """Pure decision logic. No I/O -- the clock is passed in on every call."""

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
        """Return the replica count to run, given this tick's p95 latency."""
        if p95_ms > self.up_threshold_ms:
            self._breaches += 1
            self._calm = 0
        elif p95_ms < self.down_threshold_ms:
            self._calm += 1
            self._breaches = 0
        else:
            # Between the thresholds: acceptable, so neither streak survives.
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
        return (
            self._last_scaled_at is not None
            and now - self._last_scaled_at < self.cooldown_s
        )


def run_loop(scaler, read_p95, scale, current, interval_s, should_stop, now, sleep):
    """Poll, decide, scale -- until told to stop. Returns the final count.

    Every side effect is passed in (`read_p95`, `scale`, the clock), so the
    loop is testable without Docker and the real wiring lives in main().

    `scale(n)` must return how many replicas ACTUALLY came up healthy. Module
    C's scale_to re-derives that from Docker after every action, and the loop
    carries on from the real number rather than the one it asked for.
    """
    while not should_stop():
        p95 = read_p95()
        target = scaler.decide(p95, current=current, now=now())
        if target != current:
            current = scale(target)
        sleep(interval_s)
    return current


# --- command line -----------------------------------------------------------


def parse_args(argv):
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
    return ReactiveScaler(
        min_replicas=args.min,
        max_replicas=args.max,
        up_threshold_ms=args.up_ms,
        down_threshold_ms=args.down_ms,
    )


def main(argv=None):
    """Live wiring: probe nginx, scale through Module C, tag source=reactive.

    Runs until terminated (Ctrl+C, or the comparison orchestrator stopping
    it). Not unit-tested -- it needs Docker -- but every decision it makes
    goes through run_loop and ReactiveScaler, which are.
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
        # Same knob as CASPER, tagged so the audit log separates the brains.
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
