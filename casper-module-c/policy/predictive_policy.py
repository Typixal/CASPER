"""
CASPER predictive scheduler (Module C).

This is the part that makes CASPER *predictive* rather than just a scale
controller. It reads a Prediction (Module B's output) and schedules capacity
changes off the calendar -- not off live traffic:

    at ramp_start  ->  scale UP to predicted_peak_replicas   (before traffic)
    at ramp_end    ->  scale DOWN to POST_EVENT_FLOOR_REPLICAS (gracefully)

Run it standalone:

    python policy/predictive_policy.py                       # uses the sample
    python policy/predictive_policy.py path/to/prediction.json

For a demo you do not want to wait hours for, generate a time-shifted copy of
the prediction first (see scripts/make_demo_prediction.py) and point this
script at that file:

    python scripts/make_demo_prediction.py --up-in 10 --down-in 60
    python policy/predictive_policy.py policy/demo_prediction.json

The "planned" lines printed here plus the "executed" lines the controller
writes to logs/scale_actions.jsonl together form Module C's required
predicted-event -> planned-action -> executed-action trail.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger

# Make `controller` importable when this file is run directly from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controller.scale_controller import scale_to  # noqa: E402

DEFAULT_PREDICTION_PATH = PROJECT_ROOT / "policy" / "sample_prediction.json"

# How many replicas to keep running after the event window closes.
#
# Deliberately a named constant, not a magic number, so the team can tune it.
# Note on "drain, don't kill": scale_to() finishes by reloading nginx rather
# than restarting it, so requests already in flight complete on the old
# config instead of being cut off. Keeping this floor above 0 also means the
# portal stays reachable straight after the event, when a trickle of late
# traffic is still arriving. Dropping to 0 here would be a hard cutoff and is
# not what the project means by a graceful scale-down.
POST_EVENT_FLOOR_REPLICAS = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [policy] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("casper.policy")

# APScheduler's own INFO chatter ("Adding job tentatively...", "Removed job...")
# buries our PLANNED/EXECUTING lines during a demo. Warnings still get through.
logging.getLogger("apscheduler").setLevel(logging.WARNING)


def load_prediction(path: Path) -> dict:
    """
    Read a Prediction JSON file and parse its timestamps.

    The Prediction schema is a frozen contract with Module B -- field names
    and types must not be changed here.
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

    # fromisoformat handles the "+05:30" IST offset the schema uses, so the
    # parsed datetimes stay timezone-aware and APScheduler fires at the right
    # wall-clock moment regardless of the laptop's own timezone.
    return {
        "event_id": raw["event_id"],
        "predicted_peak_replicas": int(raw["predicted_peak_replicas"]),
        "ramp_start": datetime.fromisoformat(raw["ramp_start"]),
        "ramp_peak": datetime.fromisoformat(raw["ramp_peak"]),
        "ramp_end": datetime.fromisoformat(raw["ramp_end"]),
    }


def scale_up_for_event(event_id: str, peak_replicas: int) -> None:
    """Fired at ramp_start: provision peak capacity before traffic arrives."""
    log.info("EXECUTING scale-up for %s -> %d replicas", event_id, peak_replicas)
    scale_to(peak_replicas, source="predictive")


def scale_down_after_event(event_id: str) -> None:
    """Fired at ramp_end: return to the post-event floor, gracefully."""
    log.info(
        "EXECUTING scale-down for %s -> %d replicas",
        event_id,
        POST_EVENT_FLOOR_REPLICAS,
    )
    scale_to(POST_EVENT_FLOOR_REPLICAS, source="predictive")


def schedule_prediction(prediction: dict, scheduler) -> int:
    """
    Register the scale-up and scale-down jobs for one prediction.

    Returns the number of jobs actually scheduled. Actions whose time has
    already passed are skipped with a warning rather than fired immediately,
    so an old prediction file cannot silently rescale the stack.
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

    # --- planned action 1: scale up ---
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

    # --- planned action 2: scale down ---
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
    """Load a prediction, schedule its actions, and wait for them to fire."""
    if len(sys.argv) > 2:
        print("Usage: python policy/predictive_policy.py [prediction.json]")
        return 1

    path = Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_PREDICTION_PATH
    if not path.is_absolute():
        # Allow both "policy/demo_prediction.json" from the project root and a
        # path relative to wherever the team happens to be standing.
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
        scheduler.start()  # blocks until the process is interrupted
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped by user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
