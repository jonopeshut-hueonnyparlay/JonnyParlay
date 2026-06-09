"""Tests for G_HRR_OVER_LOW_LINE (added 2026-06-09).

HRR over at line <= 0.5 is blocked: 46.3% WR (25W/29L), -25.5% sized ROI,
model overconfident -15.5pp (n=54 shadow). HRR under and HRR over at
lines > 0.5 stay in shadow accumulation.
"""

import pytest
from run_picks import check_prop_gates


def _pick(direction, line, win_prob=0.62, adj_edge=0.08, odds=-115, proj=2.1):
    return {
        "stat": "HRR", "direction": direction, "line": line,
        "sport": "MLB", "win_prob": win_prob, "adj_edge": adj_edge,
        "odds": odds, "proj": proj,
    }


# ---------------------------------------------------------------------------
# HRR over at line <= 0.5: blocked by G_HRR_OVER_LOW_LINE
# ---------------------------------------------------------------------------

def test_hrr_over_0_5_blocked():
    passed, gate = check_prop_gates(_pick("over", 0.5))
    assert not passed
    assert gate == "G_HRR_OVER_LOW_LINE"


# ---------------------------------------------------------------------------
# HRR under 0.5 and HRR over at lines > 0.5: pass through (shadow accumulation)
# ---------------------------------------------------------------------------

def test_hrr_under_0_5_passes():
    passed, gate = check_prop_gates(_pick("under", 0.5))
    assert passed, f"HRR under 0.5 should pass; blocked by {gate}"


def test_hrr_over_1_5_passes():
    passed, gate = check_prop_gates(_pick("over", 1.5))
    assert passed, f"HRR over 1.5 should pass; blocked by {gate}"


def test_hrr_over_2_5_passes():
    passed, gate = check_prop_gates(_pick("over", 2.5))
    assert passed, f"HRR over 2.5 should pass; blocked by {gate}"
