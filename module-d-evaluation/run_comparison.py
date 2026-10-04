"""Module D -- run the experiment: reactive vs predictive, same traffic.

    python run_comparison.py            # the real thing (needs Docker + k6)
    python run_comparison.py --dry-run  # print the plan, touch nothing

Sequence, for each strategy (reactive first, then predictive):

    reset the portal to the same baseline replica count
    start that strategy's scaler        (Module D reactive / Module C policy)
    replay the exam-day curve with k6   (identical both times)
    stop the scaler -- always, even if k6 fails
    collect k6's results + the scale actions from Module C's audit log

then write results/comparison.json, comparison.md and the charts.

Everything with a side effect goes through an "environment" object, so the
sequencing is tested without Docker; RealEnvironment below is the live one.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import charts
import compare
import traffic

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
STRATEGIES = ("reactive", "predictive")


@dataclass
class Plan:
    peak_rps: int
    per_replica_rps: float
    baseline_replicas: int
    lead_s: int
    warmup_s: int

    @property
    def predictive_peak(self):
        return traffic.replicas_needed(self.peak_rps, self.per_replica_rps)


def make_plan(peak_rps=250, per_replica_rps=4000 / 60, baseline_replicas=1, lead_s=20, warmup_s=5):
    """The experiment's settings.

    peak_rps 250 needs 4 replicas at the project's documented ~4000 req/min
    per replica -- sized so a laptop can run it. lead_s is how far ahead of
    the traffic ramp CASPER schedules its scale-up; it has to cover the
    seconds new containers take to pass their healthcheck.
    """
    return Plan(peak_rps, per_replica_rps, baseline_replicas, lead_s, warmup_s)


def describe(plan):
    """Human-readable plan for --dry-run."""
    return "\n".join(
        [
            "CASPER comparison plan",
            "  traffic curve   : quiet {}s -> ramp {}s -> peak {}s -> decay {}s ({}s total)".format(
                traffic.QUIET_S, traffic.RAMP_S, traffic.PEAK_S, traffic.DECAY_S, traffic.TOTAL_S
            ),
            "  peak load       : {} req/s".format(plan.peak_rps),
            "  per replica     : {:.1f} req/s (documented ~4000 req/min)".format(plan.per_replica_rps),
            "  baseline        : {} replica(s) at the start of every run".format(plan.baseline_replicas),
            "  run 1 reactive  : scales on measured p95 latency, after the fact",
            "  run 2 predictive: scales to {} replicas {}s before the ramp, from the calendar".format(
                plan.predictive_peak, plan.lead_s
            ),
            "  approx duration : {} min".format(round(2 * (traffic.TOTAL_S + 60) / 60)),
        ]
    )


def write_prediction(path, plan, k6_start):
    """A Prediction (frozen schema) aligned to this run's k6 start time."""
    ramp = k6_start + timedelta(seconds=traffic.RAMP_START_S)
    prediction = {
        "event_id": "casper_comparison_run",
        "predicted_peak_replicas": plan.predictive_peak,
        "ramp_start": (ramp - timedelta(seconds=plan.lead_s)).isoformat(),
        "ramp_peak": (ramp + timedelta(seconds=traffic.RAMP_S)).isoformat(),
        "ramp_end": (k6_start + timedelta(seconds=traffic.TOTAL_S)).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prediction, indent=2), encoding="utf-8")
    return path


def run(env, plan, out_dir=RESULTS_DIR):
    """Run both strategies against the same curve and write the comparison."""
    out = Path(out_dir)
    raw = out / "raw"
    stages = traffic.write_k6_config(raw / "stages.json", plan.peak_rps)

    runs = {}
    for strategy in STRATEGIES:
        env.reset(plan.baseline_replicas)

        k6_start = env.now() + timedelta(seconds=plan.warmup_s)
        prediction = None
        if strategy == "predictive":
            prediction = write_prediction(raw / "prediction.json", plan, k6_start)

        summary_path = raw / "{}_summary.json".format(strategy)
        csv_path = raw / "{}.csv".format(strategy)

        handle = env.start_strategy(strategy, prediction)
        try:
            wait = (k6_start - env.now()).total_seconds()
            if wait > 0:
                env.sleep(wait)
            env.run_k6(strategy, stages, summary_path, csv_path)
        finally:
            # Always: a scaler left running would keep resizing the stack.
            env.stop_strategy(handle)

        series = compare.timeseries(csv_path, bucket_s=5)
        events = compare.scale_events(
            env.audit_log(), series["start"], series["start"] + traffic.TOTAL_S, {strategy}
        )
        runs[strategy] = {
            "summary": compare.summarize_k6(json.loads(summary_path.read_text(encoding="utf-8"))),
            "series": series,
            "events": events,
            "replica_seconds": compare.replica_seconds(
                events, plan.baseline_replicas, traffic.TOTAL_S
            ),
        }

    env.reset(plan.baseline_replicas)  # leave the stack where we found it

    comparison = compare.build_comparison(runs)
    compare.write_reports(comparison, out)
    charts.render(
        comparison, out,
        ramp_start_s=traffic.RAMP_START_S,
        initial_replicas=plan.baseline_replicas,
    )
    return comparison


# --- the live environment ----------------------------------------------------


class RealEnvironment:
    """Docker via Module C's controller, the two scalers as processes, k6.exe."""

    def __init__(self):
        import module_c

        self._controller = module_c.controller()
        self._module_c = module_c.MODULE_C_DIR
        self._k6 = HERE / "tools" / "k6.exe"
        self._script = HERE / "k6" / "exam_day_traffic.js"

    def now(self):
        from datetime import datetime

        return datetime.now().astimezone()

    def sleep(self, seconds):
        import time

        time.sleep(seconds)

    def reset(self, replicas):
        print("[compare] resetting portal to {} replica(s)".format(replicas), flush=True)
        self._controller.scale_to(replicas, source="manual")

    def start_strategy(self, name, prediction_path):
        log = (RESULTS_DIR / "raw" / "{}_scaler.log".format(name)).open("w", encoding="utf-8")
        if name == "reactive":
            command = [sys.executable, str(HERE / "reactive_baseline.py")]
            cwd = HERE
        else:
            python = self._module_c / ".venv" / "Scripts" / "python.exe"
            command = [str(python), "policy/predictive_policy.py", str(prediction_path)]
            cwd = self._module_c
        print("[compare] starting {} scaler".format(name), flush=True)
        return subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)

    def stop_strategy(self, process):
        print("[compare] stopping scaler (pid {})".format(process.pid), flush=True)
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def run_k6(self, strategy, stages_path, summary_path, csv_path):
        if not self._k6.exists():
            raise FileNotFoundError(
                "k6 not found at {} -- run tools\\fetch_k6.ps1 first".format(self._k6)
            )
        print("[compare] k6 run: {} ({}s curve)".format(strategy, traffic.TOTAL_S), flush=True)
        # Absolute paths throughout: k6's open() resolves relative paths
        # against the script's folder, not the working directory.
        subprocess.run(
            [
                str(self._k6), "run", "-q",
                "-e", "STAGES_FILE={}".format(Path(stages_path).resolve()),
                "-e", "STRATEGY={}".format(strategy),
                "-e", "SUMMARY_FILE={}".format(Path(summary_path).resolve()),
                "--out", "csv={}".format(Path(csv_path).resolve()),
                str(self._script),
            ],
            check=True,
        )

    def audit_log(self):
        return self._module_c / "logs" / "scale_actions.jsonl"


def main():
    parser = argparse.ArgumentParser(description="CASPER: reactive vs predictive comparison")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    parser.add_argument("--peak-rps", type=int, default=250)
    parser.add_argument("--hold", action="store_true",
                        help="wait for Enter before exiting (used by run-demo.ps1's window)")
    args = parser.parse_args()

    plan = make_plan(peak_rps=args.peak_rps)
    print(describe(plan))
    if args.dry_run:
        return 0

    comparison = run(RealEnvironment(), plan)
    print()
    print((RESULTS_DIR / "comparison.md").read_text(encoding="utf-8"))
    print("verdict:", comparison["verdict"])
    return 0


def should_hold_window(argv):
    """Only when explicitly asked (--hold).

    run-demo.ps1 starts the real run in its own console window with --hold,
    so the result -- or the error explaining a failure -- stays on screen
    instead of vanishing the instant the run ends. Everywhere else (the
    launcher's inline --dry-run, a run from your own terminal) it must not
    stop and wait for Enter.
    """
    return "--hold" in argv


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        import traceback

        traceback.print_exc()
        code = 1
    if should_hold_window(sys.argv[1:]):
        try:
            input("\nPress Enter to close this window.")
        except EOFError:
            pass
    sys.exit(code)
