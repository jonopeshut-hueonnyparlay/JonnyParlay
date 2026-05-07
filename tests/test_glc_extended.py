#!/usr/bin/env python3
"""Tests for the extended GLC (Game-Line Correlation) gate — Change 1.

Covers:
  - Old TOTAL+TEAM_TOTAL same-direction dedup (FIX 5 backward compat)
  - ML + opposing team TEAM_TOTAL Over (tonight's BUF/MTL bug)
  - SPREAD-cover + opposing TEAM_TOTAL Over
  - F5_ML for both teams in same game
  - Alias: dedup_game_line_correlation still works
  - Prop picks are never affected by the GLC filter
  - Soft-tension pairs (ML + own TEAM_TOTAL Under) are kept
  - Multi-game slate: conflicts in game A don't affect game B
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


def _make_pick(stat, direction, is_home, game="BUF @ MTL", score=50.0, **kwargs):
    """Helper: minimal pick dict for GLC testing."""
    return {
        "stat": stat,
        "direction": direction,
        "is_home": is_home,
        "game": game,
        "pick_score": score,
        "player": kwargs.get("player", f"{stat}_{direction}_{'H' if is_home else 'A'}"),
        "sport": kwargs.get("sport", "NHL"),
        **{k: v for k, v in kwargs.items() if k not in ("player", "sport")},
    }


def _import():
    import run_picks
    return (
        run_picks.filter_game_line_correlations,
        run_picks.dedup_game_line_correlation,
    )


# ─── Backward compat: original TOTAL+TEAM_TOTAL same-direction dedup ───────────

def test_total_team_total_same_direction_drops_lower():
    """TOTAL Over + TEAM_TOTAL Over same game → drop lower pick_score (FIX 5)."""
    glc, _ = _import()
    total = _make_pick("TOTAL", "over", is_home=None, score=60.0, game="OKC @ LAL")
    tt = _make_pick("TEAM_TOTAL", "over", is_home=True, score=45.0, game="OKC @ LAL")
    result = glc([total, tt])
    stats = {p["stat"] for p in result}
    # TEAM_TOTAL should be dropped (lower score)
    assert "TOTAL" in stats
    assert "TEAM_TOTAL" not in stats


def test_total_team_total_opposite_direction_both_kept():
    """TOTAL Over + TEAM_TOTAL Under same game — not correlated, keep both."""
    glc, _ = _import()
    total = _make_pick("TOTAL", "over", is_home=None, score=60.0)
    tt = _make_pick("TEAM_TOTAL", "under", is_home=True, score=55.0)
    result = glc([total, tt])
    assert len(result) == 2


def test_alias_dedup_game_line_correlation_works():
    """Alias function returns same result as filter_game_line_correlations."""
    glc, alias = _import()
    picks = [
        _make_pick("TOTAL", "over", is_home=None, score=70.0, game="NYK @ BOS"),
        _make_pick("TEAM_TOTAL", "over", is_home=True, score=40.0, game="NYK @ BOS"),
    ]
    assert glc(picks) == alias(picks)


# ─── ML + opposing TEAM_TOTAL Over (the BUF/MTL bug) ──────────────────────────

def test_ml_fav_plus_opposing_tt_over_drops_lower():
    """BUF ML (away wins) + MTL TT Over (home scores 3+) → HARD CONFLICT, drop lower."""
    glc, _ = _import()
    buf_ml = _make_pick("ML_FAV", "win", is_home=False, score=39.6,
                        player="BUF ML", game="BUF @ MTL")
    mtl_tt = _make_pick("TEAM_TOTAL", "over", is_home=True, score=34.7,
                        player="MTL Team Total", game="BUF @ MTL")
    result = glc([buf_ml, mtl_tt])
    # BUF ML higher score → keep BUF ML, drop MTL TT
    assert len(result) == 1
    assert result[0]["player"] == "BUF ML"


def test_ml_dog_plus_opposing_tt_over_drops_lower():
    """ML_DOG for away team + home TEAM_TOTAL Over → same conflict."""
    glc, _ = _import()
    away_ml = _make_pick("ML_DOG", "win", is_home=False, score=55.0, player="MTL ML")
    home_tt = _make_pick("TEAM_TOTAL", "over", is_home=True, score=40.0, player="OKC TT")
    result = glc([away_ml, home_tt])
    assert len(result) == 1
    assert result[0]["player"] == "MTL ML"


def test_ml_same_team_tt_over_kept():
    """ML for Team A + TEAM_TOTAL Over for Team A (same team) — NOT a conflict."""
    glc, _ = _import()
    home_ml = _make_pick("ML_FAV", "win", is_home=True, score=50.0, player="LAL ML")
    home_tt = _make_pick("TEAM_TOTAL", "over", is_home=True, score=45.0, player="LAL TT")
    result = glc([home_ml, home_tt])
    assert len(result) == 2


def test_ml_plus_opposing_tt_under_kept():
    """ML for away + opponent TEAM_TOTAL Under — soft tension, both kept."""
    glc, _ = _import()
    away_ml = _make_pick("ML_FAV", "win", is_home=False, score=55.0)
    home_tt_under = _make_pick("TEAM_TOTAL", "under", is_home=True, score=50.0)
    result = glc([away_ml, home_tt_under])
    assert len(result) == 2


# ─── SPREAD-cover + opposing TEAM_TOTAL Over ──────────────────────────────────

def test_spread_cover_plus_opposing_tt_over_drops_lower():
    """Away SPREAD cover + home TEAM_TOTAL Over → HARD CONFLICT."""
    glc, _ = _import()
    spread = _make_pick("SPREAD", "cover", is_home=False, score=60.0, player="BUF +1.5")
    home_tt = _make_pick("TEAM_TOTAL", "over", is_home=True, score=38.0, player="MTL TT")
    result = glc([spread, home_tt])
    assert len(result) == 1
    assert result[0]["stat"] == "SPREAD"


# ─── F5_ML for both teams in same game ────────────────────────────────────────

def test_f5_ml_both_teams_drops_lower():
    """F5_ML for home + F5_ML for away → both can't win F5, drop lower."""
    glc, _ = _import()
    f5_home = _make_pick("F5_ML", "win", is_home=True, score=62.0, player="NYK F5 ML")
    f5_away = _make_pick("F5_ML", "win", is_home=False, score=55.0, player="PHI F5 ML")
    result = glc([f5_home, f5_away])
    assert len(result) == 1
    assert result[0]["player"] == "NYK F5 ML"


def test_f5_ml_single_team_kept():
    """F5_ML for one team only — no conflict."""
    glc, _ = _import()
    f5 = _make_pick("F5_ML", "win", is_home=True, score=55.0)
    other = _make_pick("ML_FAV", "win", is_home=True, score=50.0)
    result = glc([f5, other])
    assert len(result) == 2


# ─── Prop picks unaffected ────────────────────────────────────────────────────

def test_prop_picks_never_dropped():
    """PTS/AST/REB/SOG props are never touched by the GLC filter."""
    glc, _ = _import()
    pts = {"stat": "PTS", "direction": "over", "is_home": False,
           "game": "BUF @ MTL", "pick_score": 80.0, "player": "Caufield PTS"}
    ml = _make_pick("ML_FAV", "win", is_home=False, score=39.6, player="BUF ML")
    tt = _make_pick("TEAM_TOTAL", "over", is_home=True, score=34.7, player="MTL TT")
    result = glc([pts, ml, tt])
    # prop survives; ML wins the GLC conflict against MTL TT
    stats = {p["stat"] for p in result}
    assert "PTS" in stats
    assert "ML_FAV" in stats
    assert "TEAM_TOTAL" not in stats


# ─── Multi-game slate isolation ───────────────────────────────────────────────

def test_conflict_in_game_a_does_not_affect_game_b():
    """Conflict in BUF@MTL should not drop picks from OKC@LAL."""
    glc, _ = _import()
    buf_ml = _make_pick("ML_FAV", "win", is_home=False, score=39.6, game="BUF @ MTL")
    mtl_tt = _make_pick("TEAM_TOTAL", "over", is_home=True, score=34.7, game="BUF @ MTL")
    okc_ml = _make_pick("ML_FAV", "win", is_home=False, score=70.0, game="OKC @ LAL")
    lal_tt_under = _make_pick("TEAM_TOTAL", "under", is_home=True, score=65.0, game="OKC @ LAL")
    result = glc([buf_ml, mtl_tt, okc_ml, lal_tt_under])
    games = {p["game"] for p in result}
    assert "OKC @ LAL" in games   # OKC/LAL picks survive
    assert "BUF @ MTL" in games   # BUF ML survives
    assert len(result) == 3       # 1 dropped (MTL TT)


# ─── Synthetic BUF@MTL slate — verification checklist item 3 ──────────────────

def test_synthetic_buf_mtl_slate():
    """Reproduce tonight's BUF@MTL slate; verify GLC drops MTL TT O2.5."""
    glc, _ = _import()
    picks = [
        _make_pick("ML_FAV",     "win",   is_home=False, score=39.6,
                   player="BUF ML", game="BUF @ MTL"),
        _make_pick("TEAM_TOTAL", "over",  is_home=True,  score=34.7,
                   player="MTL Team Total", game="BUF @ MTL"),
        # Four other picks from other games (should all survive)
        _make_pick("PTS",        "over",  is_home=None,  score=75.0,
                   player="Player A PTS", game="NYK @ PHI"),
        _make_pick("AST",        "over",  is_home=None,  score=68.0,
                   player="Player B AST", game="NYK @ PHI"),
        _make_pick("ML_FAV",     "win",   is_home=True,  score=55.0,
                   player="OKC ML",       game="OKC @ SAS"),
        _make_pick("SOG",        "over",  is_home=None,  score=62.0,
                   player="Player C SOG", game="DET @ CLE"),
    ]
    result = glc(picks)
    players = [p["player"] for p in result]
    assert "BUF ML" in players            # winner kept
    assert "MTL Team Total" not in players  # dropped
    assert len(result) == 5               # 6 total − 1 dropped
