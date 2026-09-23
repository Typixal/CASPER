"""Put the module root on sys.path so tests can `import estimate` directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
