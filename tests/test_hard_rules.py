"""Tests for apply_hard_rules() — R4 (REB bans) and R11 (AST under 1.5/2.5 ban).

R11 was narrowed 2026-06-03: previously blocked all AST under ≤2.5;
now blocks only lines 1.5 and 2.5. Line 0.5 is live.
"""

import pytest
from run_picks import apply_hard_rules


def _pick(stat, direction, line):
    return {"stat": stat, "direction": direction, "line": line}


# ---------------------------------------------------------------------------
# R11: AST under
# ---------------------------------------------------------------------------

def test_r11_ast_under_0_5_passes():
    picks = [_pick("AST", "under", 0.5)]
    result = apply_hard_rules(picks)
    assert len(result) == 1


def test_r11_ast_under_1_5_blocked():
    shadow = []
    picks = [_pick("AST", "under", 1.5)]
    result = apply_hard_rules(picks, shadow_dest=shadow)
    assert len(result) == 0
    assert len(shadow) == 1
    assert shadow[0]["gate_result"] == "R11_AST_U25"


def test_r11_ast_under_2_5_blocked():
    shadow = []
    picks = [_pick("AST", "under", 2.5)]
    result = apply_hard_rules(picks, shadow_dest=shadow)
    assert len(result) == 0
    assert len(shadow) == 1
    assert shadow[0]["gate_result"] == "R11_AST_U25"


def test_r11_ast_under_3_5_passes():
    picks = [_pick("AST", "under", 3.5)]
    result = apply_hard_rules(picks)
    assert len(result) == 1


def test_r11_ast_over_2_5_passes():
    picks = [_pick("AST", "over", 2.5)]
    result = apply_hard_rules(picks)
    assert len(result) == 1


def test_r11_no_shadow_dest_silently_drops():
    picks = [_pick("AST", "under", 1.5)]
    result = apply_hard_rules(picks)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# R4: REB bans (regression)
# ---------------------------------------------------------------------------

def test_r4_reb_over_blocked():
    shadow = []
    picks = [_pick("REB", "over", 8.5)]
    result = apply_hard_rules(picks, shadow_dest=shadow)
    assert len(result) == 0
    assert shadow[0]["gate_result"] == "R4_REB_OVER"


def test_r4_reb_under_2_5_blocked():
    shadow = []
    picks = [_pick("REB", "under", 2.5)]
    result = apply_hard_rules(picks, shadow_dest=shadow)
    assert len(result) == 0
    assert shadow[0]["gate_result"] == "R4_REB_U25"


def test_r4_reb_under_3_5_passes():
    picks = [_pick("REB", "under", 3.5)]
    result = apply_hard_rules(picks)
    assert len(result) == 1
