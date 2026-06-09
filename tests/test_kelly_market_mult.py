"""Tests for KELLY_MARKET_MULT and get_market_mult() helper.

Verifies lookup priority and that sizing functions apply the multiplier
before rounding/floor/cap for straight props only.
"""

import pytest
from run_picks import get_market_mult, DEFAULT_MARKET_MULT, size_picks_base, kelly_units


# ---------------------------------------------------------------------------
# get_market_mult() lookup
# ---------------------------------------------------------------------------

def test_exact_direction_match():
    assert get_market_mult("NBA", "PTS", "over") == 0.50


def test_exact_direction_under():
    assert get_market_mult("NBA", "PTS", "under") == 1.00


def test_none_direction_fallback():
    assert get_market_mult("NHL", "SOG", "over") == 0.50
    assert get_market_mult("NHL", "SOG", "under") == 0.50


def test_none_key_in_dict():
    assert get_market_mult("NHL", "SOG", None) == 0.50


def test_team_total_none_key():
    assert get_market_mult("MLB", "TEAM_TOTAL", "over") == 0.75
    assert get_market_mult("MLB", "TEAM_TOTAL", "under") == 0.75


def test_default_fallback_unknown_sport():
    assert get_market_mult("NFL", "PTS", "over") == DEFAULT_MARKET_MULT


def test_default_fallback_unknown_stat():
    assert get_market_mult("NBA", "GOALS", "over") == DEFAULT_MARKET_MULT


def test_nba_3pm_over():
    assert get_market_mult("NBA", "3PM", "over") == 0.10


def test_nba_3pm_under():
    assert get_market_mult("NBA", "3PM", "under") == 0.75


def test_wnba_pts_no_direction():
    assert get_market_mult("WNBA", "PTS", "over") == 1.00
    assert get_market_mult("WNBA", "PTS", "under") == 1.00


def test_wnba_reb_pinned():
    """WNBA REB pinned to 0.10 both directions at go-live 2026-06-09 (None-keyed)."""
    assert get_market_mult("WNBA", "REB", "under") == 0.10
    assert get_market_mult("WNBA", "REB", "over") == 0.10


def test_mlb_outs_under():
    assert get_market_mult("MLB", "OUTS", "under") == 0.50


def test_nba_reb_under():
    assert get_market_mult("NBA", "REB", "under") == 0.50


# ---------------------------------------------------------------------------
# size_picks_base() applies market mult before floor
# ---------------------------------------------------------------------------

def _base_pick(sport, stat, direction, win_prob=0.60, odds=-110, tier="T2"):
    return {
        "sport": sport, "stat": stat, "direction": direction,
        "win_prob": win_prob, "odds": odds, "tier": tier,
    }


def test_nba_pts_over_gets_half_kelly():
    """NBA PTS over mult=0.50 → size should be smaller than default."""
    p_mult = _base_pick("NBA", "PTS", "over")
    p_default = _base_pick("NBA", "AST", "under")  # DEFAULT_MARKET_MULT=0.75
    result_mult = size_picks_base([p_mult])[0]["size"]
    result_default = size_picks_base([p_default])[0]["size"]
    # Both hit floor in many cases; check mult was applied by using a high-edge pick
    # that would clearly differ before flooring
    high_edge = _base_pick("NBA", "PTS", "over", win_prob=0.75, odds=-110)
    high_default = _base_pick("NBA", "AST", "under", win_prob=0.75, odds=-110)
    size_pts_over = size_picks_base([high_edge])[0]["size"]
    size_default = size_picks_base([high_default])[0]["size"]
    assert size_pts_over <= size_default


def test_nba_3pm_over_low_mult_hits_floor():
    """NBA 3PM over mult=0.10 → almost certainly hits T3 floor (0.25u)."""
    p = _base_pick("NBA", "3PM", "over", win_prob=0.62, odds=-110, tier="T3")
    result = size_picks_base([p])[0]["size"]
    assert result == 0.25  # should hit T3 floor


def test_wnba_reb_under_low_mult():
    """WNBA REB under mult=0.25 → smaller size for same Kelly base."""
    p_wnba = _base_pick("WNBA", "REB", "under", win_prob=0.65, odds=-110, tier="T1B")
    p_nba = _base_pick("NBA", "REB", "under", win_prob=0.65, odds=-110, tier="T1B")
    size_wnba = size_picks_base([p_wnba])[0]["size"]
    size_nba = size_picks_base([p_nba])[0]["size"]
    assert size_wnba <= size_nba
