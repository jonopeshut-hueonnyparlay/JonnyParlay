#!/usr/bin/env python3
"""Tests for audit A3 / N3 — zero-row write telemetry.

log_picks must emit a structured logger.warning whenever it writes 0 new
rows so a shadow daemon / scheduled-task review can spot silent no-ops.
"""

from __future__ import annotations

import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


@pytest.fixture
def jonnyparlay_warnings(caplog):
    """Capture WARNING+ records from the jonnyparlay logger.

    The jonnyparlay logger sets propagate=False so caplog's root handler
    never sees its records.  Attach the LogCaptureHandler directly to
    it for the duration of the test.
    """
    import run_picks
    handler = caplog.handler
    run_picks.logger.addHandler(handler)
    prev_level = run_picks.logger.level
    run_picks.logger.setLevel(logging.WARNING)
    try:
        yield caplog
    finally:
        run_picks.logger.removeHandler(handler)
        run_picks.logger.setLevel(prev_level)


def _today_et():
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _seed_29col_log(path: Path, rows=()):
    """Write a fresh pick_log with the canonical schema-v4 header."""
    header = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
        "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
        "closing_odds", "clv", "card_slot", "is_home",
        "context_verdict", "context_reason", "context_score", "legs", "over_p_raw",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            writer.writerow([r.get(c, "") for c in header])


def test_zero_qualified_input_warns(tmp_path, jonnyparlay_warnings):
    """Empty qualified list -> warning fires with qualified_in=0."""
    import run_picks
    caplog = jonnyparlay_warnings

    log_path = tmp_path / "pick_log.csv"
    _seed_29col_log(log_path)

    with caplog.at_level(logging.WARNING):
        run_picks.log_picks(
            qualified=[],
            mode="Default",
            log_path_override=log_path,
        )

    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING
                and "log_picks: 0 new rows written" in r.getMessage()]
    assert len(warnings) == 1, "expected exactly one zero-row warning"
    msg = warnings[0].getMessage()
    assert "qualified_in=0" in msg
    assert "dedup_skipped=0" in msg


def test_all_dedup_warns_with_qualified_count(tmp_path, jonnyparlay_warnings):
    """All picks dedup'd -> warning cites qualified_in=N, dedup_skipped=N."""
    import run_picks
    caplog = jonnyparlay_warnings

    log_path = tmp_path / "pick_log.csv"
    today = _today_et()
    # Seed today with two picks
    seed_rows = [
        {"date": today, "run_type": "primary", "sport": "NBA",
         "player": "Jaylen Brown", "team": "BOS", "stat": "PTS",
         "line": "23.5", "direction": "over"},
        {"date": today, "run_type": "primary", "sport": "NBA",
         "player": "LeBron James", "team": "LAL", "stat": "AST",
         "line": "7.5", "direction": "over"},
    ]
    _seed_29col_log(log_path, seed_rows)

    # Submit the same two picks (will all be dedup'd)
    qualified = [
        {"player": "Jaylen Brown", "team_abbrev": "BOS", "stat": "PTS",
         "line": 23.5, "direction": "over",
         "proj": 26.2, "win_prob": 0.58, "adj_edge": 0.07,
         "odds": -110, "book": "draftkings", "tier": "T1",
         "pick_score": 75.0, "size": 1.25, "game": "BOS @ MIA",
         "sport": "NBA", "is_home": "False"},
        {"player": "LeBron James", "team_abbrev": "LAL", "stat": "AST",
         "line": 7.5, "direction": "over",
         "proj": 8.6, "win_prob": 0.55, "adj_edge": 0.05,
         "odds": -115, "book": "draftkings", "tier": "T1",
         "pick_score": 70.0, "size": 1.0, "game": "LAL @ DEN",
         "sport": "NBA", "is_home": "False"},
    ]

    with caplog.at_level(logging.WARNING):
        run_picks.log_picks(
            qualified=qualified,
            mode="Default",
            log_path_override=log_path,
        )

    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING
                and "log_picks: 0 new rows written" in r.getMessage()]
    assert len(warnings) == 1, "expected exactly one zero-row warning"
    msg = warnings[0].getMessage()
    assert "qualified_in=2" in msg
    assert "dedup_skipped=2" in msg


def test_nonzero_write_does_not_warn(tmp_path, jonnyparlay_warnings):
    """Successful write with new rows -> no zero-row warning."""
    import run_picks
    caplog = jonnyparlay_warnings

    log_path = tmp_path / "pick_log.csv"
    _seed_29col_log(log_path)

    qualified = [{
        "player": "Anthony Edwards", "team_abbrev": "MIN", "stat": "PTS",
        "line": 27.5, "direction": "over",
        "proj": 30.1, "win_prob": 0.60, "adj_edge": 0.08,
        "odds": -110, "book": "draftkings", "tier": "T1",
        "pick_score": 80.0, "size": 1.5, "game": "MIN @ DEN",
        "sport": "NBA", "is_home": "False",
    }]

    with caplog.at_level(logging.WARNING):
        run_picks.log_picks(
            qualified=qualified,
            mode="Default",
            log_path_override=log_path,
        )

    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING
                and "log_picks: 0 new rows written" in r.getMessage()]
    assert len(warnings) == 0, "should not warn when rows were written"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
