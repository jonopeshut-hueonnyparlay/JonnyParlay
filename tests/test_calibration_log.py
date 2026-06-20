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


# ── count_calibration_days (cross-day CV gate) ────────────────────────────
def test_count_calibration_days_empty():
    from gate_check import count_calibration_days
    assert count_calibration_days([]) == 0


def test_count_calibration_days_distinct():
    """Counts distinct dates among graded calibration rows only."""
    from gate_check import count_calibration_days
    rows = [
        {"run_type": "calibration", "over_p_raw": "0.51", "result": "W", "date": "2026-06-15"},
        {"run_type": "calibration", "over_p_raw": "0.48", "result": "L", "date": "2026-06-15"},
        {"run_type": "calibration", "over_p_raw": "0.52", "result": "W", "date": "2026-06-16"},
        # excluded from the day set — ungraded / wrong run_type / no over_p_raw / blank date
        {"run_type": "calibration", "over_p_raw": "0.50", "result": "", "date": "2026-06-17"},
        {"run_type": "primary", "over_p_raw": "0.55", "result": "W", "date": "2026-06-18"},
        {"run_type": "calibration", "over_p_raw": "", "result": "W", "date": "2026-06-19"},
        {"run_type": "calibration", "over_p_raw": "0.50", "result": "W", "date": ""},
    ]
    assert count_calibration_days(rows) == 2  # only 06-15 and 06-16


def test_calibration_gate_blocked_until_min_days():
    """A single big slate satisfies the row count but not the distinct-day req."""
    from gate_check import (
        count_calibration_platt, count_calibration_days, CALIBRATION_MIN_DAYS,
    )
    one_slate = [
        {"run_type": "calibration", "over_p_raw": "0.51", "result": "W", "date": "2026-06-15"}
        for _ in range(150)
    ]
    assert count_calibration_platt(one_slate) >= 100      # primary met
    assert count_calibration_days(one_slate) == 1
    assert count_calibration_days(one_slate) < CALIBRATION_MIN_DAYS  # still blocked


def test_count_calibration_days_same_date_twice():
    """Two graded rows on the SAME calendar date collapse to one day.

    Explicit same-day-twice case (6bef685 day-boundary bug class). Also asserts
    surrounding whitespace on the date string does not spawn a phantom day —
    the counter strips before deduping.
    """
    from gate_check import count_calibration_days
    rows = [
        {"run_type": "calibration", "over_p_raw": "0.51", "result": "W", "date": "2026-06-15"},
        {"run_type": "calibration", "over_p_raw": "0.49", "result": "L", "date": " 2026-06-15 "},
    ]
    assert count_calibration_days(rows) == 1


def test_count_calibration_days_midnight_straddle():
    """A row near midnight must not double- or under-count (6bef685 bug class).

    The counter keys on the `date` calendar column, never on `run_time`. So:
      * two rows on the SAME date with run_times straddling midnight -> 1 day
        (run_time difference must NOT inflate the day count), and
      * two rows on ADJACENT dates with run_times either side of midnight -> 2
        (adjacent calendar days must NOT collapse into one).
    """
    from gate_check import count_calibration_days

    same_day = [
        {"run_type": "calibration", "over_p_raw": "0.51", "result": "W",
         "date": "2026-06-15", "run_time": "23:59:59"},
        {"run_type": "calibration", "over_p_raw": "0.48", "result": "L",
         "date": "2026-06-15", "run_time": "00:00:01"},
    ]
    assert count_calibration_days(same_day) == 1  # no double-count across midnight

    adjacent_days = [
        {"run_type": "calibration", "over_p_raw": "0.51", "result": "W",
         "date": "2026-06-15", "run_time": "23:59:59"},
        {"run_type": "calibration", "over_p_raw": "0.48", "result": "L",
         "date": "2026-06-16", "run_time": "00:00:01"},
    ]
    assert count_calibration_days(adjacent_days) == 2  # no under-count of distinct days


def test_count_calibration_days_excludes_non_iso_format():
    """Producer date-format drift must not inflate the distinct-day count.

    A non-ISO spelling of an existing day (or an unparseable format) is normalized
    away or skipped — never counted as a phantom extra day that mis-opens the gate.
    """
    from gate_check import count_calibration_days
    rows = [
        {"run_type": "calibration", "over_p_raw": "0.51", "result": "W", "date": "2026-06-15"},
        # same logical day, non-zero-padded -> normalized-to or skipped, NOT a 2nd day
        {"run_type": "calibration", "over_p_raw": "0.49", "result": "L", "date": "2026-6-15"},
        # US slash format -> unparseable -> excluded
        {"run_type": "calibration", "over_p_raw": "0.50", "result": "W", "date": "06/15/2026"},
    ]
    assert count_calibration_days(rows) == 1  # only the ISO 2026-06-15 day


def test_count_calibration_days_all_iso_unchanged():
    """The normal all-ISO producer case still counts each distinct day exactly."""
    from gate_check import count_calibration_days
    rows = [
        {"run_type": "calibration", "over_p_raw": "0.51", "result": "W",
         "date": f"2026-06-{d:02d}"}
        for d in range(15, 25)  # 10 distinct ISO days
    ]
    assert count_calibration_days(rows) == 10


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
