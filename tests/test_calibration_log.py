#!/usr/bin/env python3
"""Tests for the calibration shadow log (Platt refit acceleration).

Covers:
  * gate_check.count_calibration_platt counting semantics
  * paths.PICK_LOG_CALIBRATION_PATH is importable / correctly named
  * regression: log_picks() honors the run_type param (was hard-coded
    "primary" at the writerow site — see pick_log_writers.py).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

# engine/ is added to sys.path by the repo-root conftest.py.


# ── count_calibration_platt ──────────────────────────────────────────────
def test_count_calibration_platt_empty():
    from gate_check import count_calibration_platt
    assert count_calibration_platt([]) == 0


def test_count_calibration_platt_filters():
    """Counts only calibration rows that are graded W/L with over_p_raw."""
    from gate_check import count_calibration_platt
    rows = [
        # counted
        {"run_type": "calibration", "over_p_raw": "0.5123", "result": "W"},
        {"run_type": "calibration", "over_p_raw": "0.4810", "result": "L"},
        # excluded — wrong run_type
        {"run_type": "primary", "over_p_raw": "0.5500", "result": "W"},
        # excluded — empty over_p_raw
        {"run_type": "calibration", "over_p_raw": "", "result": "W"},
        # excluded — ungraded
        {"run_type": "calibration", "over_p_raw": "0.5000", "result": ""},
        # excluded — push / void are not W/L
        {"run_type": "calibration", "over_p_raw": "0.5000", "result": "P"},
        {"run_type": "calibration", "over_p_raw": "0.5000", "result": "VOID"},
    ]
    assert count_calibration_platt(rows) == 2


# ── path constant ────────────────────────────────────────────────────────
def test_calibration_path_importable():
    from paths import PICK_LOG_CALIBRATION_PATH
    assert Path(PICK_LOG_CALIBRATION_PATH).name == "pick_log_calibration.csv"


# ── regression: log_picks honors run_type ────────────────────────────────
def _sample_prop():
    return {
        "player": "Anthony Edwards", "team_abbrev": "MIN", "stat": "PTS",
        "line": 27.5, "direction": "over",
        "proj": 30.1, "win_prob": 0.60, "adj_edge": 0.08,
        "odds": -110, "book": "draftkings", "tier": "T2",
        "pick_score": 80.0, "size": 1.5, "game": "MIN @ DEN",
        "sport": "NBA", "is_home": "False",
        "pick_type": "prop", "over_p_raw": 0.5123,
    }


def _read_one(path: Path) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1, f"expected exactly one row, got {len(rows)}"
    return rows[0]


def test_log_picks_writes_calibration_run_type(tmp_path):
    """run_type='calibration' must reach the CSV (was hard-coded 'primary')."""
    import run_picks
    log_path = tmp_path / "pick_log_calibration.csv"
    run_picks.log_picks(
        [_sample_prop()], "Default",
        log_path_override=log_path,
        run_type="calibration",
    )
    row = _read_one(log_path)
    assert row["run_type"] == "calibration"
    assert row["over_p_raw"] == "0.5123"


def test_log_picks_default_run_type_is_primary(tmp_path):
    """Default callers (no run_type) keep writing 'primary' — no regression."""
    import run_picks
    log_path = tmp_path / "pick_log.csv"
    run_picks.log_picks([_sample_prop()], "Default", log_path_override=log_path)
    row = _read_one(log_path)
    assert row["run_type"] == "primary"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
