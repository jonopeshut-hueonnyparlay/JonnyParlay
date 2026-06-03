"""Tests for value_parlay: 5-leg fallback parlay that fires when 6-leg longshot cannot build.

Covers: build_value_parlay, VALUE_PARLAY_SIZE, per-game cap, per-player dedup,
        ordering by win_prob, combined_prob calculation.
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


def _five_picks_five_games():
    """5 picks, each from a different game and different player — all pass caps."""
    games = [f"Team{i} @ Team{i+1}" for i in range(5)]
    return [_pick(0.70 - i * 0.01, games[i], player=f"Player{i}") for i in range(5)]


def _six_picks_two_games():
    """6 picks: 3 from game A, 3 from game B.
    Per-game cap of 2 → at most 2+2=4 legs → <5 → None.
    """
    return (
        [_pick(0.75, "OKC @ DEN", player=f"P_A{i}") for i in range(3)]
        + [_pick(0.72, "MIN @ LAL", player=f"P_B{i}") for i in range(3)]
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestValueParlayConstants:
    def test_size_is_025(self):
        assert rp.VALUE_PARLAY_SIZE == 0.25


# ---------------------------------------------------------------------------
# build_value_parlay
# ---------------------------------------------------------------------------

class TestBuildValueParlay:
    def test_returns_none_on_empty_pool(self):
        assert rp.build_value_parlay([]) is None

    def test_returns_none_if_fewer_than_5(self):
        picks = [_pick(0.70, f"G{i} @ H{i}", player=f"P{i}") for i in range(4)]
        assert rp.build_value_parlay(picks) is None

    def test_builds_from_5_unique_picks(self):
        picks = _five_picks_five_games()
        result = rp.build_value_parlay(picks)
        assert result is not None
        assert len(result["legs"]) == 5

    def test_per_game_cap_returns_none_when_pool_too_small(self):
        """3+3 across 2 games: cap of 2 per game → max 4 legs → None."""
        result = rp.build_value_parlay(_six_picks_two_games())
        assert result is None

    def test_per_player_dedup_blocks_same_player_twice(self):
        """4 unique players + 1 player appearing twice (PTS + REB) → only 1 leg from that player → 5 total passes."""
        picks = [_pick(0.70, f"G{i} @ H{i}", player=f"P{i}") for i in range(4)]
        picks.append(_pick(0.80, "G4 @ H4", player="StarPlayer", stat="PTS"))
        picks.append(_pick(0.79, "G4 @ H4", player="StarPlayer", stat="REB"))
        result = rp.build_value_parlay(picks)
        assert result is not None
        assert len(result["legs"]) == 5
        star_legs = [l for l in result["legs"] if l["player"] == "StarPlayer"]
        assert len(star_legs) == 1

    def test_selects_highest_win_prob(self):
        """7 picks across 7 games — top 5 by WP should be selected."""
        games = [f"Team{i} @ Team{i+1}" for i in range(7)]
        picks = [_pick(0.70 - i * 0.01, games[i], player=f"Player{i}") for i in range(7)]
        result = rp.build_value_parlay(picks)
        assert result is not None
        assert len(result["legs"]) == 5
        wp_values = [l["win_prob"] for l in result["legs"]]
        assert min(wp_values) >= picks[4]["win_prob"] - 1e-9

    def test_combined_prob_is_product(self):
        """5 picks each with win_prob=0.70 → combined ≈ 0.70^5."""
        picks = [_pick(0.70, f"G{i} @ H{i}", player=f"P{i}") for i in range(5)]
        result = rp.build_value_parlay(picks)
        assert result is not None
        expected = 0.70 ** 5
        assert abs(result["combined_prob"] - expected) < 1e-9

    def test_parlay_odds_field_present(self):
        picks = _five_picks_five_games()
        result = rp.build_value_parlay(picks)
        assert result is not None
        assert "parlay_odds" in result

    def test_result_keys(self):
        picks = _five_picks_five_games()
        result = rp.build_value_parlay(picks)
        assert result is not None
        assert set(result.keys()) == {"legs", "combined_prob", "parlay_odds", "book"}

    def test_not_built_when_longshot_succeeds(self):
        """Call-site guard: value_parlay should be None when safest6 can be built."""
        six_picks = [_pick(0.70 - i * 0.01, f"G{i} @ H{i}", player=f"P{i}") for i in range(6)]
        longshot = rp.build_safest6_parlay(six_picks)
        assert longshot is not None
        # Simulate call-site logic
        value_parlay = rp.build_value_parlay(six_picks) if longshot is None else None
        assert value_parlay is None
