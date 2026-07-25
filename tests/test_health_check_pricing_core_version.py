"""ADR-005 / 1C (revised per architecture review) -- health_check.py's
pricing_core version-visibility line.

Pure informational stamp, not a pass/fail check -- see health_check.py's own
comment for why an import-failure branch was deliberately dropped (pricing_core
is a hard dependency of ~28 files; a broken install already crashes run_picks.py
loudly on startup, so a health-report warning would add code without adding
real detection value). This test only confirms the happy-path visibility line
actually appears -- there's no failure branch left to test.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
HEALTH_CHECK = ENGINE_DIR / "health_check.py"


def test_pricing_core_version_is_printed():
    proc = subprocess.run(
        [sys.executable, str(HEALTH_CHECK)],
        cwd=str(ENGINE_DIR.parent),
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "pricing_core version:" in proc.stdout
    # pricing_core is a real installed dependency in this environment -- confirm
    # a real version string printed, not a silently-swallowed "unknown".
    assert "pricing_core version: unknown" not in proc.stdout
