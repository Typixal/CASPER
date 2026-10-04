"""Write a copy of a Prediction shifted to fire a few seconds from now.

Lets the predictive policy be demonstrated live instead of on the real event
date. Kept separate from the policy so the policy only ever reads real times.

Examples:
    python scripts/make_demo_prediction.py --up-in 10 --down-in 60 --peak 4
    python policy/predictive_policy.py policy/demo_prediction.json
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = PROJECT_ROOT / "policy" / "sample_prediction.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "policy" / "demo_prediction.json"


def main() -> None:
    """Parse arguments and write the shifted prediction."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Prediction file to copy (default: policy/sample_prediction.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the shifted copy (default: policy/demo_prediction.json)",
    )
    parser.add_argument(
        "--up-in",
        type=int,
        default=15,
        help="Seconds from now until ramp_start (the scale-up). Default 15.",
    )
    parser.add_argument(
        "--down-in",
        type=int,
        default=90,
        help="Seconds from now until ramp_end (the scale-down). Default 90.",
    )
    parser.add_argument(
        "--peak",
        type=int,
        default=None,
        help="Override predicted_peak_replicas (handy on a laptop that cannot "
        "comfortably run 12 containers).",
    )
    args = parser.parse_args()

    if args.down_in <= args.up_in:
        parser.error("--down-in must be greater than --up-in")

    with args.source.open(encoding="utf-8") as handle:
        prediction = json.load(handle)

    # Local time with its offset, to keep the schema's ISO-8601-with-offset form.
    now = datetime.now().astimezone()
    ramp_start = now + timedelta(seconds=args.up_in)
    ramp_end = now + timedelta(seconds=args.down_in)
    ramp_peak = ramp_start + (ramp_end - ramp_start) / 2

    prediction["ramp_start"] = ramp_start.isoformat()
    prediction["ramp_peak"] = ramp_peak.isoformat()
    prediction["ramp_end"] = ramp_end.isoformat()
    if args.peak is not None:
        prediction["predicted_peak_replicas"] = args.peak

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(prediction, handle, indent=2)
        handle.write("\n")

    print("Wrote {}".format(args.output))
    print("  ramp_start : {}".format(prediction["ramp_start"]))
    print("  ramp_peak  : {}".format(prediction["ramp_peak"]))
    print("  ramp_end   : {}".format(prediction["ramp_end"]))
    print("  peak       : {} replicas".format(prediction["predicted_peak_replicas"]))
    print()
    print("Now run:  python policy/predictive_policy.py {}".format(args.output))


if __name__ == "__main__":
    main()
