"""Predictive scheduler: scales from a Prediction's calendar, not live traffic.

    at ramp_start -> scale up to predicted_peak_replicas
    at ramp_end   -> scale down to POST_EVENT_FLOOR_REPLICAS

The PLANNED lines logged here and the executed actions in
logs/scale_actions.jsonl form the predicted -> planned -> executed audit trail.

Usage:
    python policy/predictive_policy.py [prediction.json]

For a live demo, time-shift a prediction first with
scripts/make_demo_prediction.py.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controller.scale_controller import scale_to  # noqa: E402

DEFAULT_PREDICTION_PATH = PROJECT_ROOT / "policy" / "sample_prediction.json"

# Kept above 0 so late traffic after the window is still served.
POST_EVENT_FLOOR_REPLICAS = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [policy] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("casper.policy")

# APScheduler's INFO chatter buries the PLANNED/EXECUTING lines.
logging.getLogger("apscheduler").setLevel(logging.WARNING)


def load_prediction(path: Path) -> dict:
    """Read a Prediction file (frozen schema) and parse its timestamps.

    Args:
        path: Prediction JSON file.

    Returns:
        The prediction with ramp_* fields as timezone-aware datetimes.

    Raises:
        ValueError: If a required field is missing.
    """
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)

    required = [
        "event_id",
        "predicted_peak_replicas",
        "ramp_start",
        "ramp_peak",
        "ramp_end",
    ]
    missing = [field for field in required if field not in raw]
    if missing:
        raise ValueError(
            "Prediction file {} is missing required field(s): {}".format(
                path, ", ".join(missing)
            )
        )

    # Keeping the +05:30 offset makes jobs fire at the right moment whatever
    # the laptop's timezone.
    return {
        "event_id": raw["event_id"],
        "predicted_peak_replicas": int(raw["predicted_peak_replicas"]),
        "ramp_start": datetime.fromisoformat(raw["ramp_start"]),
        "ramp_peak": datetime.fromisoformat(raw["ramp_peak"]),
        "ramp_end": datetime.fromisoformat(raw["ramp_end"]),
    }


def scale_up_for_event(event_id: str, peak_replicas: int) -> None:
    """Job fired at ramp_start: provision peak capacity ahead of traffic."""
    log.info("EXECUTING scale-up for %s -> %d replicas", event_id, peak_replicas)
    scale_to(peak_replicas, source="predictive")


def scale_down_after_event(event_id: str) -> None:
    """Job fired at ramp_end: drain back to the post-event floor."""
    log.info(
        "EXECUTING scale-down for %s -> %d replicas",
        event_id,
        POST_EVENT_FLOOR_REPLICAS,
    )
    scale_to(POST_EVENT_FLOOR_REPLICAS, source="predictive")


def schedule_prediction(prediction: dict, scheduler) -> int:
    """Register the scale-up and scale-down jobs for one prediction.

    Actions already in the past are skipped, not fired, so a stale file
    cannot rescale the stack.

    Args:
        prediction: Output of load_prediction().
        scheduler: An APScheduler scheduler.

    Returns:
        Number of jobs scheduled (0-2).
    """
    event_id = prediction["event_id"]
    peak = prediction["predicted_peak_replicas"]
    now = datetime.now(prediction["ramp_start"].tzinfo)
    scheduled = 0

    log.info(
        "Loaded prediction for %s: peak=%d replicas, window %s -> %s (peak at %s)",
        event_id,
        peak,
        prediction["ramp_start"].isoformat(),
        prediction["ramp_end"].isoformat(),
        prediction["ramp_peak"].isoformat(),
    )

    if prediction["ramp_start"] > now:
        scheduler.add_job(
            scale_up_for_event,
            trigger=DateTrigger(run_date=prediction["ramp_start"]),
            args=[event_id, peak],
            id="{}_scale_up".format(event_id),
            replace_existing=True,
        )
        log.info(
            "PLANNED: at %s scale UP to %d replicas (event %s)",
            prediction["ramp_start"].isoformat(),
            peak,
            event_id,
        )
        scheduled += 1
    else:
        log.warning(
            "SKIPPED scale-up: ramp_start %s is already in the past. "
            "Use scripts/make_demo_prediction.py for a demo run.",
            prediction["ramp_start"].isoformat(),
        )

    if prediction["ramp_end"] > now:
        scheduler.add_job(
            scale_down_after_event,
            trigger=DateTrigger(run_date=prediction["ramp_end"]),
            args=[event_id],
            id="{}_scale_down".format(event_id),
            replace_existing=True,
        )
        log.info(
            "PLANNED: at %s scale DOWN to %d replicas (event %s)",
            prediction["ramp_end"].isoformat(),
            POST_EVENT_FLOOR_REPLICAS,
            event_id,
        )
        scheduled += 1
    else:
        log.warning(
            "SKIPPED scale-down: ramp_end %s is already in the past.",
            prediction["ramp_end"].isoformat(),
        )

    return scheduled


def main() -> int:
    """Load a prediction, schedule its jobs and block until interrupted.

    Returns:
        Process exit code.
    """
    if len(sys.argv) > 2:
        print("Usage: python policy/predictive_policy.py [prediction.json]")
        return 1

    path = Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_PREDICTION_PATH
    if not path.is_absolute():
        # Resolve against the project root first, then the working directory.
        candidate = (PROJECT_ROOT / path).resolve()
        path = candidate if candidate.exists() else path.resolve()

    if not path.exists():
        log.error("Prediction file not found: %s", path)
        return 1

    prediction = load_prediction(path)

    scheduler = BlockingScheduler()
    if schedule_prediction(prediction, scheduler) == 0:
        log.error("Nothing left to schedule -- every action is in the past.")
        return 1

    log.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped by user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
