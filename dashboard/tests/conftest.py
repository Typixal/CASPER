"""Put the dashboard root on sys.path so tests can import the collector."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
