"""H3 hardening -- health_check.py's new EDGEMODEL_DB_PATH existence check.

health_check.py is a linear top-to-bottom script (not a set of importable
functions), and is already consumed as a subprocess by run_picks.py's health
gate (see tests/test_health_gate.py, which mocks that subprocess entirely).
Matching that existing pattern, these tests run the real script as a
subprocess with a controlled EDGEMODEL_DB_PATH env var and assert on stdout,
rather than trying to import/unit-test individual lines out of a script body.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
HEALTH_CHECK = ENGINE_DIR / "health_check.py"


def _run_health_check(env_overrides: dict[str, str]) -> str:
    import os
    env = dict(os.environ)
    env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(HEALTH_CHECK)],
        cwd=str(ENGINE_DIR.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout


def test_warns_on_missing_edgemodel_db_path(tmp_path):
    missing = tmp_path / "does_not_exist" / "projections.db"
    out = _run_health_check({"EDGEMODEL_DB_PATH": str(missing)})
    assert "EDGEMODEL_DB_PATH resolves to a missing file" in out
    assert str(missing) in out


def test_passes_when_edgemodel_db_path_exists(tmp_path):
    """health_check.py only itemizes FAIL/WARN in its printed report -- a
    passing check is silent by design, only reflected in the summary count.
    So the correct assertion here is the negative: no warning fires."""
    real = tmp_path / "projections.db"
    real.write_bytes(b"")  # existence is all the check requires
    out = _run_health_check({"EDGEMODEL_DB_PATH": str(real)})
    assert "EDGEMODEL_DB_PATH resolves to a missing file" not in out
