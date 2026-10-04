"""Bridge from Module D into Module C's shared scale controller.

Both scaling brains must turn the SAME knob -- that is the experimental
control. So Module D imports Module C's real controller rather than
re-implementing scaling. The path is resolved from this file's location, so
it works no matter which directory Module D is launched from.
"""

import importlib
import sys
from pathlib import Path

MODULE_C_DIR = Path(__file__).resolve().parent.parent / "casper-module-c"


def controller():
    """Return Module C's scale_controller module (import-safe by design)."""
    root = str(MODULE_C_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module("controller.scale_controller")
