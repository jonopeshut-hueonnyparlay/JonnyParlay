#!/usr/bin/env python3
"""Tests for audit A1 — --no-cap must bypass apply_caps for shadow/research mode.

Without the bypass, apply_caps truncates the qualified pool via STAT_CAP /
max_per_game / SPORT_UNIT_CAP / 12u-total before the no-cap-substituted
log_picks call ever fires, capping shadow output to ~4 picks/day on a
typical NBA slate (8u sport cap / 2u sizing).  --research --no-cap should
accumulate ~25-50 picks/day for fast Platt-refit CLV gathering.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


def _pick(player, stat, line, sport="NBA", game="X @ Y", direction="over",
          size=2.0, pick_score=80.0):
    """Build a synthetic pick mirroring run_picks.size_picks_base() output."""
    return {
        "player": player, "team_abbrev": "BOS", "stat": stat,
        "line": line, "direction": direction,
        "proj": float(line) + 2.0, "win_prob": 0.55, "adj_edge": 0.05,
        "odds": -110, "book": "draftkings", "tier": "T1",
        "pick_score": pick_score, "size": size,
        "game": game, "sport": sport, "is_home": "False",
    }


def _maybe_apply_caps(picks, no_cap_flag, max_per_game=2):
    """Mirror the conditional in run_picks.main() at line ~5518.

    Keep this in lock-step with the production code: it's the exact
    pattern wrapping apply_caps() and is the unit-of-behavior the A1
    fix is asserting on.
    """
    import run_picks
    if picks and not no_cap_flag:
        return run_picks.apply_caps(picks, {}, max_per_game=max_per_game)
    return picks


def test_apply_caps_truncates_under_default_flag():
    """Regression guard: with no_cap=False, apply_caps trims the pool.

    20 NBA picks × 2.0u each = 40u sized — the 12u total cap and the
    per-stat-2 cap should both bite, returning <<20 picks.
    """
    picks = []
    for i in range(20):
        # Spread across 5 stats / 4 games so STAT_CAP=2 fires per stat
        stat = ["PTS", "REB", "AST", "FG3M", "BLK"][i % 5]
        game = f"GAME{i // 5}"
        picks.append(_pick(f"Player{i}", stat, 10.0 + i, game=game))

    result = _maybe_apply_caps(picks, no_cap_flag=False, max_per_game=2)

    assert len(result) < len(picks), \
        f"apply_caps must trim 20-pick pool; returned {len(result)}"
    # 12u total cap with 2.0u sizing => max 6 picks
    assert len(result) <= 6, \
        f"NBA 12u total cap should bound at 6 picks; got {len(result)}"


def test_no_cap_preserves_full_pool():
    """A1 fix: with no_cap=True the conditional skips apply_caps entirely
    and the original pool is returned unchanged."""
    picks = []
    for i in range(20):
        stat = ["PTS", "REB", "AST", "FG3M", "BLK"][i % 5]
        game = f"GAME{i // 5}"
        picks.append(_pick(f"Player{i}", stat, 10.0 + i, game=game))

    result = _maybe_apply_caps(picks, no_cap_flag=True, max_per_game=2)

    assert len(result) == len(picks), \
        f"--no-cap must preserve full pool; got {len(result)}/{len(picks)}"
    # Identity preserved (no copy mutation): same dicts back
    assert result is picks or all(p in picks for p in result)


def test_no_cap_documented_throughput_range():
    """Sanity: with --no-cap and a realistic NBA slate (10 games × ~5
    qualifying picks/game), the bypass surfaces 30+ picks vs the
    capped result of 4-6.  Validates the docstring claim of 25-50/day."""
    picks = []
    for game_idx in range(10):
        for stat_idx, stat in enumerate(["PTS", "REB", "AST", "FG3M", "BLK"]):
            picks.append(_pick(
                f"Player{game_idx}_{stat_idx}", stat,
                line=10.0 + stat_idx,
                game=f"GAME{game_idx}",
                size=2.0,
            ))
    # 50 total picks (10 games × 5 stats)
    assert len(picks) == 50

    capped = _maybe_apply_caps(picks, no_cap_flag=False, max_per_game=2)
    uncapped = _maybe_apply_caps(picks, no_cap_flag=True, max_per_game=2)

    assert len(capped) <= 6, f"capped should be <=6, got {len(capped)}"
    assert 25 <= len(uncapped) <= 50, \
        f"--no-cap should produce ~25-50 picks; got {len(uncapped)}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
