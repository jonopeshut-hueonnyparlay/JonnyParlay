"""R16 hardening -- health_check.py's new SaberSim NBA CSV availability check.

Mirrors odds_io.py::parse_csv()'s own Downloads search (12h window). Uses the
same subprocess pattern as tests/test_health_check_edgemodel_db_path.py.
Path.home() resolves via USERPROFILE on Windows, so overriding it in the
subprocess env gives an isolated, controllable "Downloads" directory without
touching the real one. Confirmed health_check.py uses Path.home()/USERPROFILE
nowhere else, so this override cannot affect any other check in the same run.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
HEALTH_CHECK = ENGINE_DIR / "health_check.py"


def _run_health_check(env_overrides: dict[str, str]) -> str:
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


def test_warns_when_no_recent_nba_csv(tmp_path):
    # "Checking SaberSim NBA CSV availability..." always prints (every
    # category's announcement line does, pass or fail) -- the WARN detail
    # text is the actual differentiator, matching the WARN case.
    (tmp_path / "Downloads").mkdir()
    out = _run_health_check({"USERPROFILE": str(tmp_path)})
    assert "no recent NBA export found" in out


def test_passes_when_recent_nba_csv_present(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "sabersim_nba.csv").write_text("Name,PTS\nA,20\n", encoding="utf-8")
    out = _run_health_check({"USERPROFILE": str(tmp_path)})
    # health_check.py only itemizes FAIL/WARN in its printed report -- a
    # passing check is silent by design (see test_health_check_edgemodel_db_path.py).
    assert "no recent NBA export found" not in out
