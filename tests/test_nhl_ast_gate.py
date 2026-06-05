"""Tests for NHL AST 0.5 under activation.

G8 is exempted for NHL AST 0.5 under.
G_NHL_AST blocks all other NHL AST lines/directions.
"""

import pytest
from run_picks import check_prop_gates


def _pick(stat, direction, line, sport="NHL", win_prob=0.60, adj_edge=0.09, odds=-115, proj=0.3):
    return {
        "stat": stat, "direction": direction, "line": line,
        "sport": sport, "win_prob": win_prob, "adj_edge": adj_edge,
        "odds": odds, "proj": proj,
    }


# ---------------------------------------------------------------------------
# NHL AST 0.5 under: should PASS all gates
# ---------------------------------------------------------------------------

def test_nhl_ast_0_5_under_passes_g8():
    passed, gate = check_prop_gates(_pick("AST", "under", 0.5))
    assert gate != "G8", f"Expected G8 exemption, got {gate}"


def test_nhl_ast_0_5_under_passes_gnhl_ast():
    passed, gate = check_prop_gates(_pick("AST", "under", 0.5))
    assert gate != "G_NHL_AST", f"Expected G_NHL_AST exemption, got {gate}"


def test_nhl_ast_0_5_under_passes_overall():
    passed, gate = check_prop_gates(_pick("AST", "under", 0.5))
    assert passed, f"NHL AST 0.5 under should pass; blocked by {gate}"


# ---------------------------------------------------------------------------
# NHL AST non-0.5 or non-under: blocked by G_NHL_AST
# ---------------------------------------------------------------------------

def test_nhl_ast_1_5_under_blocked():
    # line=1.5 <= 1.5 → G8 fires (not G_NHL_AST, which handles lines > 1.5)
    passed, gate = check_prop_gates(_pick("AST", "under", 1.5))
    assert not passed
    assert gate == "G8"


def test_nhl_ast_2_5_under_blocked():
    passed, gate = check_prop_gates(_pick("AST", "under", 2.5))
    assert not passed
    assert gate == "G_NHL_AST"


def test_nhl_ast_3_5_under_blocked():
    passed, gate = check_prop_gates(_pick("AST", "under", 3.5))
    assert not passed
    assert gate == "G_NHL_AST"


def test_nhl_ast_1_5_over_blocked():
    passed, gate = check_prop_gates(_pick("AST", "over", 1.5))
    # G8B fires for AST over <= 4.5 (sport != WNBA) before G_NHL_AST
    assert not passed


def test_nhl_ast_0_5_over_blocked():
    # over at line 0.5 → G8B blocks (AST over <= 4.5, sport != WNBA)
    passed, gate = check_prop_gates(_pick("AST", "over", 0.5))
    assert not passed


# ---------------------------------------------------------------------------
# Regression: NBA AST 0.5 under still blocked by G8
# ---------------------------------------------------------------------------

def test_nba_ast_0_5_under_still_blocked_by_g8():
    pick = _pick("AST", "under", 0.5, sport="NBA")
    passed, gate = check_prop_gates(pick)
    assert not passed
    assert gate == "G8"


# ---------------------------------------------------------------------------
# Regression: non-AST stats still blocked by G8 at line 0.5
# ---------------------------------------------------------------------------

def test_reb_0_5_under_still_blocked_by_g8():
    pick = _pick("REB", "under", 0.5, sport="NBA")
    passed, gate = check_prop_gates(pick)
    assert not passed
    assert gate == "G8"
