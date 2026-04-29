"""Tests for Apr 28 2026 longshot redesign: 6-leg parlay, per-game cap of 2.

Audit H11 — zero coverage existed before this file.
Covers: build_longshot_parlay, LONGSHOT_MAX_PER_GAME, LONGSHOT_SIZE.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
import run_picks as rp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick(win_prob=0.70, game="OKC @ DEN", player="Player A",
          stat="PTS", direction="OVER", line=25.5, team="OKC"):
    return {
        "win_prob":  win_prob,
        "game":      game,
        "player":    player,
        "stat":      stat,
        "direction": direction,
        "line":      line,
        "team":      team,
    }


def _six_picks_two_games():
    """6 picks: 3 from game A, 3 from game B.
    Per-game cap of 2 means only 2 from each game → <6 → returns None.
    """
    return (
        [_pick(0.75, "OKC @ DEN")] * 3   # 3 from game A
        + [_pick(0.72, "MIN @ LAL")] * 3  # 3 from game B
    )


def _six_picks_six_games():
    """6 picks, each from a different game — all pass the per-game cap."""
    games = [f"Team{i} @ Team{i+1}" for i in range(6)]
    return [_pick(0.70 - i * 0.01, games[i]) for i in range(6)]


def _seven_picks_six_games():
    """7 picks across 6 games — top 6 by WP should be selected."""
    games = [f"Team{i} @ Team{i+1}" for i in range(6)]
    picks = [_pick(0.70 - i * 0.01, games[i]) for i in range(6)]
    picks.append(_pick(0.60, games[0]))  # 7th: low WP, same game as first
    return picks


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestLongshotConstants:
    def test_size_is_025(self):
        assert rp.LONGSHOT_SIZE == 0.25


# ---------------------------------------------------------------------------
# build_longshot_parlay
# ---------------------------------------------------------------------------

class TestBuildLongshotParlay:
    def test_returns_none_if_fewer_than_6_qualified(self):
        result = rp.build_safest6_parlay([_pick()] * 5)
        assert result is None

    def test_returns_none_on_empty_input(self):
        assert rp.build_safest6_parlay([]) is None

    def test_six_from_six_games_returns_parlay(self):
        result = rp.build_safest6_parlay(_six_picks_six_games())
        assert result is not None
        assert "legs" in result
        assert len(result["legs"]) == 6

    def test_per_game_cap_of_2_blocks_third_from_same_game(self):
        """3+ picks from same game → 3rd is skipped → can't reach 6 legs → None."""
        result = rp.build_safest6_parlay(_six_picks_two_games())
        # 3 from game A → 2 allowed + 3 from game B → 2 allowed = 4 legs, need 6 → None
        assert result is None

    def test_per_game_cap_exactly_2_passes(self):
        """2 picks per game, 3 games → exactly 6 legs → valid parlay."""
        games = ["OKC @ DEN", "MIN @ LAL", "PHX @ GSW"]
        picks = [_pick(0.70, g) for g in games for _ in range(2)]
        result = rp.build_safest6_parlay(picks)
        assert result is not None
        assert len(result["legs"]) == 6

    def test_selects_highest_wp_picks(self):
        """build_longshot_parlay ranks by win_prob descending."""
        picks = _seven_picks_six_games()
        result = rp.build_safest6_parlay(picks)
        assert result is not None
        # The low-WP 7th pick (WP=0.60) should NOT be in the legs
        # (first pick from its game was already taken with WP=0.70)
        wps = [l["win_prob"] for l in result["legs"]]
        assert 0.60 not in wps

    def test_result_has_combined_prob(self):
        result = rp.build_safest6_parlay(_six_picks_six_games())
        assert "combined_prob" in result
        assert 0 < result["combined_prob"] < 1

    def test_combined_prob_is_product_of_wps(self):
        picks = _six_picks_six_games()
        result = rp.build_safest6_parlay(picks)
        expected = 1.0
        for l in result["legs"]:
            expected *= l["win_prob"]
        assert abs(result["combined_prob"] - expected) < 1e-9

    def test_result_has_parlay_odds(self):
        result = rp.build_safest6_parlay(_six_picks_six_games())
        assert "parlay_odds" in result

    def test_six_high_prob_picks_one_game_fails(self):
        """All 6 from one game → cap kills 4 of them → only 2 legs → None."""
        picks = [_pick(0.80, "OKC @ DEN")] * 6
        assert rp.build_safest6_parlay(picks) is None

    def test_mixed_cap_scenario_enough_games(self):
        """2 per game, 4 games = 8 picks available; selects top 6."""
        games = [f"G{i} @ G{i+1}" for i in range(4)]
        picks = []
        for i, g in enumerate(games):
            picks.append(_pick(0.80 - i * 0.02, g))
            picks.append(_pick(0.75 - i * 0.02, g))
        assert len(picks) == 8
        result = rp.build_safest6_parlay(picks)
        assert result is not None
        assert len(result["legs"]) == 6
        # Verify no game appears more than 2 times
        from collections import Counter
        game_counts = Counter(l["game"] for l in result["legs"])
        assert max(game_counts.values()) <= 2
