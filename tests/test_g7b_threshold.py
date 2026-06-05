"""Tests for G7b soft-juice threshold raise: 9% → 10% (2026-06-05).

G7b blocks picks with odds in [-149, -140] and edge < 10%.
Picks at exactly 10% should pass G7b.
"""

import pytest
from run_picks import check_prop_gates


def _pick(stat="PTS", direction="over", line=25.5, win_prob=0.65,
          adj_edge=0.10, odds=-145, proj=27.0, sport="NBA"):
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


def test_g7b_9pct_soft_juice_now_blocked():
    """9% edge at -145 was live before; now blocked by G7b."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.09, odds=-145))
    assert not passed
    assert gate == "G7b"


def test_g7b_9_5pct_soft_juice_blocked():
    """9.5% edge at -142 is still below the new 10% threshold."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.095, odds=-142))
    assert not passed
    assert gate == "G7b"


def test_g7b_exactly_10pct_passes():
    """10% edge at -145 clears G7b."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.10, odds=-145))
    assert gate != "G7b"


def test_g7b_above_10pct_passes():
    """11% edge at -148 clears G7b."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.11, odds=-148))
    assert gate != "G7b"


def test_g7b_odds_below_range_not_blocked():
    """Odds of -135 are outside G7b range; 5% edge only hits G9."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.05, odds=-135))
    assert gate != "G7b"


def test_g7b_hard_juice_blocked_by_g7_not_g7b():
    """-155 odds → G7 (hard juice), not G7b."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.15, odds=-155))
    assert not passed
    assert gate == "G7"


def test_g7b_boundary_minus140_low_edge_blocked():
    """Exactly -140 odds with 9% edge → G7b."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.09, odds=-140))
    assert not passed
    assert gate == "G7b"


def test_g7b_boundary_minus149_low_edge_blocked():
    """Exactly -149 odds with 9% edge → G7b."""
    passed, gate = check_prop_gates(_pick(adj_edge=0.09, odds=-149))
    assert not passed
    assert gate == "G7b"
