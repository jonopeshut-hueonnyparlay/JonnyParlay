"""pytest conftest — makes engine/ importable from tests/ without per-file sys.path hacks."""
import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent / "engine"
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))
