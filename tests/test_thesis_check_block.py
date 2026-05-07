#!/usr/bin/env python3
"""Tests for print_thesis_block (Change 3).

The thesis block prints a per-game comparison of pre-GLC vs post-GLC
game-line picks so Jono can see what was dropped and why.

Covers:
  - Output printed when a game has ≥2 game-line picks pre-GLC
  - Output includes ✓ for survived picks and ✗ for dropped
  - No output when no game has ≥2 game-line picks
  - Prop picks are excluded from the thesis block
  - Multi-game slate shows both games
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


def _block(pre, post, capsys):
    import run_picks
    run_picks.print_thesis_block(pre, post)
    return capsys.readouterr().out


def _gl(stat, direction, is_home, game, score=50.0, player=None):
    return {
        "stat": stat,
        "direction": direction,
        "is_home": is_home,
        "game": game,
        "pick_score": score,
        "player": player or f"{stat}_{direction}",
    }


# ─── Basic output ──────────────────────────────────────────────────────────────

def test_thesis_fires_for_multi_pick_game(capsys):
    """When game has ≥2 picks pre-GLC, block is printed."""
    ml = _gl("ML_FAV", "win", False, "BUF @ MTL", score=39.6, player="BUF ML")
    tt = _gl("TEAM_TOTAL", "over", True, "BUF @ MTL", score=34.7, player="MTL TT")
    out = _block([ml, tt], [ml], capsys)   # TTL dropped in post
    assert "Thesis Check" in out
    assert "BUF @ MTL" in out


def test_thesis_marks_survivor_with_checkmark(capsys):
    """Survived pick shows ✓."""
    ml = _gl("ML_FAV", "win", False, "BUF @ MTL", score=39.6, player="BUF ML")
    tt = _gl("TEAM_TOTAL", "over", True, "BUF @ MTL", score=34.7, player="MTL TT")
    out = _block([ml, tt], [ml], capsys)
    # BUF ML survived
    assert "✓" in out


def test_thesis_marks_dropped_pick_with_x(capsys):
    """Dropped pick shows ✗ and DROPPED marker."""
    ml = _gl("ML_FAV", "win", False, "BUF @ MTL", score=39.6, player="BUF ML")
    tt = _gl("TEAM_TOTAL", "over", True, "BUF @ MTL", score=34.7, player="MTL TT")
    out = _block([ml, tt], [ml], capsys)
    assert "✗" in out
    assert "DROPPED" in out


def test_thesis_no_output_for_single_pick_game(capsys):
    """Game with only 1 game-line pick pre-GLC → no thesis output."""
    ml = _gl("ML_FAV", "win", False, "BUF @ MTL", score=39.6, player="BUF ML")
    out = _block([ml], [ml], capsys)
    assert "Thesis Check" not in out


def test_thesis_no_output_when_no_gl_picks(capsys):
    """No game-line picks at all → no output."""
    prop = {"stat": "PTS", "direction": "over", "is_home": None,
            "game": "BUF @ MTL", "pick_score": 80.0, "player": "Caufield PTS"}
    out = _block([prop], [prop], capsys)
    assert "Thesis Check" not in out


# ─── Prop isolation ───────────────────────────────────────────────────────────

def test_props_excluded_from_thesis(capsys):
    """Prop picks don't count toward the ≥2 threshold and aren't shown."""
    prop = {"stat": "PTS", "direction": "over", "is_home": None,
            "game": "BUF @ MTL", "pick_score": 80.0, "player": "Caufield PTS"}
    ml = _gl("ML_FAV", "win", False, "BUF @ MTL", score=39.6, player="BUF ML")
    # Only 1 game-line pick → no thesis block
    out = _block([prop, ml], [prop, ml], capsys)
    assert "Thesis Check" not in out


# ─── Multi-game slate ─────────────────────────────────────────────────────────

def test_thesis_shows_both_games(capsys):
    """Multi-game slate: thesis block shows each game with ≥2 GL picks."""
    buf_ml = _gl("ML_FAV",     "win",  False, "BUF @ MTL", score=39.6, player="BUF ML")
    mtl_tt = _gl("TEAM_TOTAL", "over", True,  "BUF @ MTL", score=34.7, player="MTL TT")
    okc_ml = _gl("ML_FAV",     "win",  False, "OKC @ LAL", score=70.0, player="OKC ML")
    lal_tt = _gl("TEAM_TOTAL", "under",True,  "OKC @ LAL", score=65.0, player="LAL TT")
    # Both games have 2 GL picks pre-GLC; assume OKC game has no conflict
    out = _block(
        [buf_ml, mtl_tt, okc_ml, lal_tt],
        [buf_ml,          okc_ml, lal_tt],   # MTL TT dropped
        capsys,
    )
    assert "BUF @ MTL" in out
    assert "OKC @ LAL" in out


# ─── Integration: GLC + thesis block together ─────────────────────────────────

def test_integration_glc_then_thesis(capsys):
    """Run filter_game_line_correlations then print_thesis_block and verify output."""
    import run_picks
    ml  = _gl("ML_FAV",     "win",  False, "BUF @ MTL", score=39.6, player="BUF ML")
    tt  = _gl("TEAM_TOTAL", "over", True,  "BUF @ MTL", score=34.7, player="MTL TT")
    pre = [ml, tt]
    post = run_picks.filter_game_line_correlations(pre)
    run_picks.print_thesis_block(pre, post)
    out = capsys.readouterr().out
    assert "✓" in out       # BUF ML survived
    assert "✗" in out       # MTL TT dropped
    assert "DROPPED" in out
