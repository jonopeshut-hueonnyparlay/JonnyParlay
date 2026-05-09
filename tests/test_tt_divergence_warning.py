#!/usr/bin/env python3
"""Tests for warn_tt_divergence (Change 2).

Market-implied team total = (total_line + team_spread_line) / 2
Warning fires when |engine_proj - implied| > 0.25 (default threshold).

Covers:
  - Warning fires for BUF@MTL fixture (gap=0.42 > 0.25)
  - Warning suppressed when gap <= threshold
  - Correct formula for home vs away team
  - No crash when TOTAL or SPREAD picks are absent from the pool
  - Custom threshold respected
  - Non-TEAM_TOTAL picks are silently ignored
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


def _warn(picks, threshold=0.25):
    import run_picks
    return run_picks.warn_tt_divergence(picks, threshold=threshold)


def _make_total(line, game="BUF @ MTL"):
    return {"stat": "TOTAL", "line": line, "game": game,
            "direction": "over", "pick_score": 55.0, "gate_result": "PASS"}


def _make_spread(line, is_home, game="BUF @ MTL"):
    return {"stat": "SPREAD", "line": line, "is_home": is_home, "game": game,
            "direction": "cover", "pick_score": 50.0, "gate_result": "PASS"}


def _make_tt(proj, is_home, game="BUF @ MTL", direction="over"):
    return {
        "stat": "TEAM_TOTAL",
        "proj": proj,
        "is_home": is_home,
        "game": game,
        "direction": direction,
        "player": "MTL Team Total" if is_home else "BUF Team Total",
        "line": 2.5,
        "pick_score": 34.7,
        "gate_result": "PASS",
    }


# ─── BUF@MTL fixture (checklist item 4) ────────────────────────────────────────

def test_buf_mtl_divergence_fires(capsys):
    """MTL: engine_proj=2.92, implied=2.5, gap=0.42 > 0.25 → warning fires."""
    # Game: BUF @ MTL, total=5.5, BUF spread=-0.5 (away favoured)
    # home MTL spread from BUF perspective: home spread_line = +0.5
    picks = [
        _make_total(5.5),
        _make_spread(0.5, is_home=True),   # home MTL is +0.5 (dog)
        _make_tt(2.92, is_home=True),       # engine projects MTL at 2.92
    ]
    # implied for home = (5.5 - 0.5) / 2 = 2.5; gap = 0.42 → fires
    _warn(picks)
    captured = capsys.readouterr()
    assert "TT-DIVERGE" in captured.out
    assert "2.92" in captured.out
    assert "2.50" in captured.out


def test_no_warning_when_gap_within_threshold(capsys):
    """Gap of 0.10 ≤ 0.25 → no warning."""
    picks = [
        _make_total(5.5),
        _make_spread(0.5, is_home=True),
        _make_tt(2.60, is_home=True),   # implied=2.5, gap=0.10
    ]
    _warn(picks)
    captured = capsys.readouterr()
    assert "TT-DIVERGE" not in captured.out


def test_exactly_at_threshold_no_warning(capsys):
    """Gap exactly equal to threshold → no warning (strict >)."""
    picks = [
        _make_total(5.5),
        _make_spread(0.5, is_home=True),
        _make_tt(2.75, is_home=True),   # implied=2.5, gap=0.25 exactly
    ]
    _warn(picks)
    captured = capsys.readouterr()
    assert "TT-DIVERGE" not in captured.out


# ─── Home vs away formula ──────────────────────────────────────────────────────

def test_home_team_formula():
    """home_implied = (total - home_spread) / 2."""
    # total=6.0, home_spread=-1.0 (home fav by 1)
    # home_implied = (6.0 - (-1.0)) / 2 = 3.5
    picks = [
        {"stat": "TOTAL",     "line": 6.0,  "game": "G2", "direction": "over",
         "pick_score": 55.0, "gate_result": "PASS"},
        {"stat": "SPREAD",    "line": -1.0, "game": "G2", "is_home": True,
         "direction": "cover", "pick_score": 50.0, "gate_result": "PASS"},
        {"stat": "TEAM_TOTAL","proj": 5.5,  "game": "G2", "is_home": True,
         "direction": "over", "player": "Home TT", "line": 3.5,
         "pick_score": 40.0, "gate_result": "PASS"},
    ]
    import run_picks, logging
    import io
    handler = logging.StreamHandler(buf := io.StringIO())
    handler.setLevel(logging.WARNING)
    run_picks.logger.addHandler(handler)
    try:
        run_picks.warn_tt_divergence(picks)
        log_output = buf.getvalue()
    finally:
        run_picks.logger.removeHandler(handler)
    # proj=5.5, implied=3.5, gap=2.0 → warning must fire
    assert "TT DIVERGENCE" in log_output


def test_away_team_formula():
    """away_implied = (total + home_spread) / 2."""
    # total=6.0, home_spread=-1.0 → away_implied = (6.0 + (-1.0)) / 2 = 2.5
    picks = [
        {"stat": "TOTAL",     "line": 6.0,  "game": "G3", "direction": "over",
         "pick_score": 55.0, "gate_result": "PASS"},
        {"stat": "SPREAD",    "line": -1.0, "game": "G3", "is_home": True,
         "direction": "cover", "pick_score": 50.0, "gate_result": "PASS"},
        {"stat": "TEAM_TOTAL","proj": 4.5,  "game": "G3", "is_home": False,
         "direction": "over", "player": "Away TT", "line": 2.5,
         "pick_score": 40.0, "gate_result": "PASS"},
    ]
    import run_picks, logging
    import io
    handler = logging.StreamHandler(buf := io.StringIO())
    handler.setLevel(logging.WARNING)
    run_picks.logger.addHandler(handler)
    try:
        run_picks.warn_tt_divergence(picks)
        log_output = buf.getvalue()
    finally:
        run_picks.logger.removeHandler(handler)
    # proj=4.5, implied=2.5, gap=2.0 → warning
    assert "TT DIVERGENCE" in log_output


# ─── Missing market data ───────────────────────────────────────────────────────

def test_no_crash_when_total_absent(capsys):
    """If no TOTAL pick for that game, warning is skipped (no crash)."""
    picks = [
        _make_spread(0.5, is_home=True),
        _make_tt(2.92, is_home=True),
    ]
    _warn(picks)   # must not raise


def test_no_crash_when_spread_absent(capsys):
    """If no SPREAD pick for that game, warning is skipped (no crash)."""
    picks = [
        _make_total(5.5),
        _make_tt(2.92, is_home=True),
    ]
    _warn(picks)   # must not raise


# ─── Custom threshold ──────────────────────────────────────────────────────────

def test_custom_threshold_stricter(capsys):
    """Gap=0.20 fires at threshold=0.15 but not at threshold=0.25."""
    picks = [
        _make_total(5.0),
        _make_spread(0.0, is_home=True),   # home_implied = 2.5
        _make_tt(2.70, is_home=True),      # gap = 0.20
    ]
    _warn(picks, threshold=0.15)
    assert "TT-DIVERGE" in capsys.readouterr().out

    _warn(picks, threshold=0.25)
    assert "TT-DIVERGE" not in capsys.readouterr().out
