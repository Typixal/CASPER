"""Bridge to Module C's scale controller, so both strategies turn the same knob."""

import importlib
import sys
from pathlib import Path

MODULE_C_DIR = Path(__file__).resolve().parent.parent / "casper-module-c"


def controller():
    """Import and return Module C's controller.scale_controller module."""
    root = str(MODULE_C_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module("controller.scale_controller")
