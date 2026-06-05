"""Tests for G9 (universal 5% edge floor) and G9B (NBA 7% edge floor).

G9 raised from 3% → 5% (2026-06-05).
G9B added: NBA props require ≥7% edge.
Game lines (check_game_gates / GG3) are unaffected.
"""

import pytest
from run_picks import check_prop_gates


def _pick(stat="PTS", direction="over", line=25.5, win_prob=0.60,
          adj_edge=0.06, odds=-115, proj=27.0, sport="NBA"):
    return {
        "stat": stat,
        "direction": direction,
        "line": line,
        "win_prob": win_prob,
        "adj_edge": adj_edge,
        "odds": odds,
        "proj": proj,
        "sport": sport,
    }


# ---------------------------------------------------------------------------
# G9: universal 5% floor
# ---------------------------------------------------------------------------

def test_g9_edge_below_5pct_blocked():
    """4% edge → G9 regardless of sport."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.04, sport="NHL"))
    assert not passed
    assert gate == "G9"


def test_g9_old_3pct_no_longer_passes():
    """3.5% edge was live before; now blocked by G9."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.035, sport="NHL"))
    assert not passed
    assert gate == "G9"


def test_g9_exactly_5pct_not_blocked_by_g9():
    """5% edge clears G9 (but NBA picks then hit G9B at <7%)."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.05, sport="NHL"))
    # NHL: G9 passes, no G9B — should pass all gates with this pick shape
    assert gate != "G9"


# ---------------------------------------------------------------------------
# G9B: NBA-specific 7% floor
# ---------------------------------------------------------------------------

def test_g9b_nba_6pct_blocked():
    """6% NBA edge clears G9 (≥5%) but hits G9B (<7%)."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.06, sport="NBA"))
    assert not passed
    assert gate == "G9B"


def test_g9b_nba_exactly_7pct_passes():
    """7% NBA edge clears both G9 and G9B."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.07, sport="NBA"))
    assert gate not in ("G9", "G9B")


def test_g9b_nba_above_7pct_passes():
    """8% NBA edge clears both G9 and G9B."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.08, sport="NBA"))
    assert gate not in ("G9", "G9B")


def test_g9b_nhl_6pct_not_blocked():
    """G9B is NBA-only; 6% NHL edge should not trigger it."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.06, sport="NHL"))
    assert gate != "G9B"


def test_g9b_mlb_6pct_not_blocked():
    """G9B is NBA-only; 6% MLB edge should not trigger it."""
    passed, gate = check_prop_gates(_pick(stat="OUTS", direction="over",
                                         line=5.5, adj_edge=0.06,
                                         sport="MLB", proj=6.0))
    assert gate != "G9B"


def test_g9b_wnba_6pct_not_blocked():
    """G9B is NBA-only; WNBA has its own G_WNBA_EDGE gate."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.06, sport="WNBA"))
    assert gate != "G9B"
