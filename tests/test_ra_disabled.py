"""Tests for G_RA_DISABLED gate.

RA (REB+AST combo) disabled 2026-06-05: 0W/7L (0% actual WR vs 56.7% model, n=11).
"""

import pytest
from run_picks import check_prop_gates


def _pick(stat, direction="over", line=24.5, sport="NBA", win_prob=0.60,
          adj_edge=0.07, odds=-115, proj=25.0):
    return {
        "stat": stat, "direction": direction, "line": line,
        "sport": sport, "win_prob": win_prob, "adj_edge": adj_edge,
        "odds": odds, "proj": proj,
    }


# ---------------------------------------------------------------------------
# RA blocked in both directions
# ---------------------------------------------------------------------------

def test_ra_over_blocked():
    passed, gate = check_prop_gates(_pick("RA", "over", line=24.5, proj=26.0))
    assert not passed
    assert gate == "G_RA_DISABLED"


def test_ra_under_blocked():
    passed, gate = check_prop_gates(_pick("RA", "under", line=24.5, proj=22.0))
    assert not passed
    assert gate == "G_RA_DISABLED"


# ---------------------------------------------------------------------------
# Other combo stats unaffected
# ---------------------------------------------------------------------------

def test_pr_not_blocked_by_ra_gate():
    pick = _pick("PR", "over", line=30.5, proj=32.0, adj_edge=0.07, win_prob=0.62)
    passed, gate = check_prop_gates(pick)
    assert gate != "G_RA_DISABLED"


def test_pa_not_blocked_by_ra_gate():
    pick = _pick("PA", "over", line=30.5, proj=32.0, adj_edge=0.07, win_prob=0.62)
    passed, gate = check_prop_gates(pick)
    assert gate != "G_RA_DISABLED"


def test_pra_not_blocked_by_ra_gate():
    pick = _pick("PRA", "over", line=40.5, proj=43.0, adj_edge=0.07, win_prob=0.62)
    passed, gate = check_prop_gates(pick)
    assert gate != "G_RA_DISABLED"
