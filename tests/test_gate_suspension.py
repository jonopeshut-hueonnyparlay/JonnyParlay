"""Tests for full-stat suspension gates G_SOG_SUSPENDED and G_HA_SUSPENDED.

Both gates added 2026-06-05 pending distribution investigation.
G_SOG_SUSPENDED supersedes G8C (SOG under ≤3.5).
G_HA_SUSPENDED supersedes G_HA_DIR (HA over block).
"""

import pytest
from run_picks import check_prop_gates


def _pick(stat, direction, line=3.5, win_prob=0.60, adj_edge=0.06, odds=-115, proj=4.0, sport="NHL"):
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
# G_SOG_SUSPENDED
# ---------------------------------------------------------------------------

def test_sog_over_blocked():
    passed, gate = check_prop_gates(_pick("SOG", "over", line=4.5))
    assert not passed
    assert gate == "G_SOG_SUSPENDED"


def test_sog_under_blocked():
    passed, gate = check_prop_gates(_pick("SOG", "under", line=3.5))
    assert not passed
    assert gate == "G_SOG_SUSPENDED"


def test_sog_under_high_line_blocked():
    """SOG under at line > 3.5 (was previously live) is also suspended."""
    passed, gate = check_prop_gates(_pick("SOG", "under", line=5.5))
    assert not passed
    assert gate == "G_SOG_SUSPENDED"


# ---------------------------------------------------------------------------
# G_HA_SUSPENDED
# ---------------------------------------------------------------------------

def test_ha_under_blocked():
    """HA under was previously live (only overs were blocked); now suspended."""
    passed, gate = check_prop_gates(_pick("HA", "under", line=7.5, sport="MLB"))
    assert not passed
    assert gate == "G_HA_SUSPENDED"


def test_ha_over_blocked():
    passed, gate = check_prop_gates(_pick("HA", "over", line=7.5, sport="MLB"))
    assert not passed
    assert gate == "G_HA_SUSPENDED"


# ---------------------------------------------------------------------------
# Regression: non-suspended stats still pass gates they previously passed
# ---------------------------------------------------------------------------

def test_hits_under_not_suspended():
    """HITS under is a separate stat — G_HA_SUSPENDED must not affect it."""
    pick = _pick("HITS", "under", line=1.5, win_prob=0.62, adj_edge=0.07, odds=-110, proj=1.2, sport="MLB")
    passed, gate = check_prop_gates(pick)
    # HITS under 1.5 hits G8 (binary fragility) — not G_HA_SUSPENDED
    assert gate != "G_HA_SUSPENDED"
