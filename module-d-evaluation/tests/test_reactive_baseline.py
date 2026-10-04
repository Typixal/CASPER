"""Tests for the reactive baseline's scaling decisions and control loop."""

import reactive_baseline as rb

SLOW = 600.0   # above the 400 ms scale-up threshold
CALM = 80.0    # below the 150 ms scale-down threshold
MIDDLE = 250.0  # between the two


def make_scaler(**overrides):
    settings = dict(
        min_replicas=1,
        max_replicas=6,
        up_threshold_ms=400,
        down_threshold_ms=150,
        up_after=2,
        down_after=6,
        step_up=2,
        step_down=1,
        cooldown_s=15,
    )
    settings.update(overrides)
    return rb.ReactiveScaler(**settings)


def test_a_single_slow_reading_does_not_trigger_a_scale_up():
    scaler = make_scaler()

    assert scaler.decide(SLOW, current=1, now=0) == 1


def test_two_consecutive_slow_readings_scale_up_by_the_step():
    scaler = make_scaler()
    scaler.decide(SLOW, current=1, now=0)

    assert scaler.decide(SLOW, current=1, now=5) == 3


def test_a_normal_reading_resets_the_breach_streak():
    scaler = make_scaler()
    scaler.decide(SLOW, current=1, now=0)
    scaler.decide(MIDDLE, current=1, now=5)

    assert scaler.decide(SLOW, current=1, now=10) == 1


def test_scale_up_never_exceeds_the_maximum():
    scaler = make_scaler(max_replicas=4)
    scaler.decide(SLOW, current=3, now=0)

    assert scaler.decide(SLOW, current=3, now=5) == 4


def test_sustained_calm_scales_down_by_one():
    scaler = make_scaler()
    for tick in range(5):
        assert scaler.decide(CALM, current=4, now=tick * 5) == 4

    assert scaler.decide(CALM, current=4, now=25) == 3


def test_scale_down_never_goes_below_the_minimum():
    scaler = make_scaler(min_replicas=1)
    for tick in range(6):
        target = scaler.decide(CALM, current=1, now=tick * 5)

    assert target == 1


def test_no_further_scaling_inside_the_cooldown_after_a_scale_action():
    # New replicas need time to become healthy; acting again first is thrash.
    scaler = make_scaler(cooldown_s=15)
    scaler.decide(SLOW, current=1, now=0)
    assert scaler.decide(SLOW, current=1, now=5) == 3  # scaled at t=5

    scaler.decide(SLOW, current=3, now=10)
    assert scaler.decide(SLOW, current=3, now=15) == 3  # still cooling down


def test_scaling_resumes_once_the_cooldown_has_passed():
    scaler = make_scaler(cooldown_s=15)
    scaler.decide(SLOW, current=1, now=0)
    scaler.decide(SLOW, current=1, now=5)  # scaled at t=5

    scaler.decide(SLOW, current=3, now=21)
    assert scaler.decide(SLOW, current=3, now=26) == 5


def test_the_middle_band_holds_steady():
    scaler = make_scaler()
    for tick in range(10):
        assert scaler.decide(MIDDLE, current=3, now=tick * 5) == 3


class FakeClock:
    """A clock that advances only when the loop sleeps."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def run_for(ticks, p95_readings, scale, start=1):
    clock = FakeClock()
    readings = iter(p95_readings)
    done = {"n": 0}

    def should_stop():
        done["n"] += 1
        return done["n"] > ticks

    return rb.run_loop(
        make_scaler(),
        read_p95=lambda: next(readings),
        scale=scale,
        current=start,
        interval_s=5,
        should_stop=should_stop,
        now=clock.now,
        sleep=clock.sleep,
    )


def test_the_loop_scales_up_after_sustained_slow_readings():
    requested = []

    run_for(2, [SLOW, SLOW], scale=lambda n: requested.append(n) or n)

    assert requested == [3]


def test_the_loop_trusts_the_actual_healthy_count_not_the_request():
    # Only 2 of the requested 3 came up; the loop must continue from 2.
    final = run_for(2, [SLOW, SLOW], scale=lambda n: 2)

    assert final == 2


def test_the_loop_does_not_call_scale_when_nothing_changes():
    requested = []

    run_for(4, [MIDDLE] * 4, scale=lambda n: requested.append(n) or n)

    assert requested == []


def test_the_loop_stops_when_asked():
    final = run_for(0, [], scale=lambda n: n, start=3)

    assert final == 3


def test_cli_defaults_probe_the_nginx_entrypoint_every_five_seconds():
    args = rb.parse_args([])

    assert args.url == "http://localhost:8080/results"
    assert args.interval == 5


def test_cli_settings_reach_the_scaler():
    args = rb.parse_args(["--max", "8", "--up-ms", "300"])
    scaler = rb.scaler_from_args(args)

    assert scaler.max_replicas == 8
    assert scaler.up_threshold_ms == 300
