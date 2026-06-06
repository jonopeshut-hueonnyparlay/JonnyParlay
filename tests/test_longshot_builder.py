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
    """6 picks, each from a different game and different player — all pass caps."""
    games = [f"Team{i} @ Team{i+1}" for i in range(6)]
    return [_pick(0.70 - i * 0.01, games[i], player=f"Player{i}") for i in range(6)]


def _seven_picks_six_games():
    """7 picks across 6 games — top 6 by WP should be selected."""
    games = [f"Team{i} @ Team{i+1}" for i in range(6)]
    picks = [_pick(0.70 - i * 0.01, games[i], player=f"Player{i}") for i in range(6)]
    picks.append(_pick(0.60, games[0], player="PlayerX"))  # 7th: low WP, same game as first
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
        picks = [_pick(0.70, f"G{i} @ H{i}", player=f"P{i}") for i in range(5)]
        result = rp.build_safest6_parlay(picks)
        assert result is None

    def test_player_dedup_blocks_same_player_twice(self):
        """Same player appearing for two stats in same game: only 1 leg allowed."""
        # 5 unique players in 5 games + same player twice in a 6th game → only 1 from that player
        picks = [_pick(0.70, f"G{i} @ H{i}", player=f"P{i}") for i in range(5)]
        picks.append(_pick(0.80, "G5 @ H5", player="StarPlayer", stat="PTS"))
        picks.append(_pick(0.79, "G5 @ H5", player="StarPlayer", stat="REB"))
        result = rp.build_safest6_parlay(picks)
        # 5 unique players + only 1 leg from StarPlayer = 6 legs total
        assert result is not None
        assert len(result["legs"]) == 6
        star_legs = [l for l in result["legs"] if l["player"] == "StarPlayer"]
        assert len(star_legs) == 1

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
        """2 picks per game, 3 games, unique players → exactly 6 legs → valid parlay."""
        games = ["OKC @ DEN", "MIN @ LAL", "PHX @ GSW"]
        picks = [
            _pick(0.70, games[i], player=f"P{i}{j}")
            for i in range(3) for j in range(2)
        ]
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
        """2 per game, 4 games, unique players = 8 picks available; selects top 6."""
        games = [f"G{i} @ G{i+1}" for i in range(4)]
        picks = []
        for i, g in enumerate(games):
            picks.append(_pick(0.80 - i * 0.02, g, player=f"P{i}A"))
            picks.append(_pick(0.75 - i * 0.02, g, player=f"P{i}B"))
        assert len(picks) == 8
        result = rp.build_safest6_parlay(picks)
        assert result is not None
        assert len(result["legs"]) == 6
        # Verify no game appears more than 2 times
        from collections import Counter
        game_counts = Counter(l["game"] for l in result["legs"])
        assert max(game_counts.values()) <= 2


# ---------------------------------------------------------------------------
# Plan 9 §9B: positive-ρ ranking boost (OUTS under + opposing TT over)
# ---------------------------------------------------------------------------

def _corr_pick(win_prob, game, player, stat, direction, team_abbrev):
    p = _pick(win_prob, game, player=player, stat=stat, direction=direction)
    p["team_abbrev"] = team_abbrev
    return p


class TestLongshotRhoBoost:
    def test_rho_constant(self):
        assert rp.LONGSHOT_PAIR_RHO == 0.35

    def test_pair_detector_positive(self):
        a = _corr_pick(0.80, "MIL @ CHC", "Pitcher", "OUTS", "under", "CHC")
        b = _corr_pick(0.70, "MIL @ CHC", "", "TEAM_TOTAL", "over", "MIL")
        assert rp._longshot_pos_corr_pair(a, b)
        assert rp._longshot_pos_corr_pair(b, a)  # order-independent

    def test_pair_detector_same_team_negative(self):
        """Pitcher's OWN team total over is NOT the boosted pair."""
        a = _corr_pick(0.80, "MIL @ CHC", "Pitcher", "OUTS", "under", "CHC")
        b = _corr_pick(0.70, "MIL @ CHC", "", "TEAM_TOTAL", "over", "CHC")
        assert not rp._longshot_pos_corr_pair(a, b)

    def test_pair_detector_different_game_negative(self):
        a = _corr_pick(0.80, "MIL @ CHC", "Pitcher", "OUTS", "under", "CHC")
        b = _corr_pick(0.70, "NYY @ BOS", "", "TEAM_TOTAL", "over", "NYY")
        assert not rp._longshot_pos_corr_pair(a, b)

    def test_pair_detector_wrong_directions_negative(self):
        a = _corr_pick(0.80, "MIL @ CHC", "Pitcher", "OUTS", "over", "CHC")
        b = _corr_pick(0.70, "MIL @ CHC", "", "TEAM_TOTAL", "over", "MIL")
        assert not rp._longshot_pos_corr_pair(a, b)

    def test_effective_wp_equals_raw_without_pair(self):
        p = _pick(0.72, "G1 @ G2", player="P1")
        others = [_pick(0.80, "G3 @ G4", player="P2")]
        assert rp._longshot_effective_wp(p, others) == 0.72

    def test_effective_wp_boosted_with_pair(self):
        """Effective wp = min(0.99, (p·q + ρ·sqrt(p(1−p)q(1−q))) / q) > raw wp."""
        import math
        outs = _corr_pick(0.82, "MIL @ CHC", "Pitcher", "OUTS", "under", "CHC")
        tt = _corr_pick(0.70, "MIL @ CHC", "", "TEAM_TOTAL", "over", "MIL")
        eff = rp._longshot_effective_wp(tt, [outs])
        joint = 0.70 * 0.82 + 0.35 * math.sqrt(0.70 * 0.30 * 0.82 * 0.18)
        assert eff == pytest.approx(min(0.99, joint / 0.82))
        assert eff > 0.70

    def test_boosted_partner_enters_the_six(self):
        """A TT-over leg below the raw-wp cutoff makes the 6 via the +ρ pair."""
        base = [_pick(0.80 - i * 0.01, f"G{i} @ H{i}", player=f"P{i}")
                for i in range(4)]  # 0.80, 0.79, 0.78, 0.77 in distinct games
        outs = _corr_pick(0.82, "MIL @ CHC", "Pitcher", "OUTS", "under", "CHC")
        tt = _corr_pick(0.70, "MIL @ CHC", "", "TEAM_TOTAL", "over", "MIL")
        marginal = _pick(0.76, "G9 @ H9", player="P9")   # raw-wp 6th place
        filler = _pick(0.745, "G8 @ H8", player="P8")
        picks = base + [outs, tt, marginal, filler]
        result = rp.build_safest6_parlay(picks)
        assert result is not None
        wps = [l["win_prob"] for l in result["legs"]]
        # TT boosted: eff ≈ 0.775 > 0.76 → displaces the marginal pick
        assert 0.70 in wps, "boosted TT leg should be selected"
        assert 0.76 not in wps, "marginal raw-wp pick should be displaced"

    def test_same_team_tt_not_boosted(self):
        """Same scenario but TT on the pitcher's own team → no boost → no entry."""
        base = [_pick(0.80 - i * 0.01, f"G{i} @ H{i}", player=f"P{i}")
                for i in range(4)]
        outs = _corr_pick(0.82, "MIL @ CHC", "Pitcher", "OUTS", "under", "CHC")
        tt = _corr_pick(0.70, "MIL @ CHC", "", "TEAM_TOTAL", "over", "CHC")  # same team
        marginal = _pick(0.76, "G9 @ H9", player="P9")
        filler = _pick(0.745, "G8 @ H8", player="P8")
        picks = base + [outs, tt, marginal, filler]
        result = rp.build_safest6_parlay(picks)
        assert result is not None
        wps = [l["win_prob"] for l in result["legs"]]
        assert 0.70 not in wps
        assert 0.76 in wps

    def test_combined_prob_stays_independence_product(self):
        """Even with a boosted pair, logged combined_prob is the raw product."""
        base = [_pick(0.80 - i * 0.01, f"G{i} @ H{i}", player=f"P{i}")
                for i in range(4)]
        outs = _corr_pick(0.82, "MIL @ CHC", "Pitcher", "OUTS", "under", "CHC")
        tt = _corr_pick(0.70, "MIL @ CHC", "", "TEAM_TOTAL", "over", "MIL")
        marginal = _pick(0.76, "G9 @ H9", player="P9")
        filler = _pick(0.745, "G8 @ H8", player="P8")
        result = rp.build_safest6_parlay(base + [outs, tt, marginal, filler])
        expected = 1.0
        for l in result["legs"]:
            expected *= l["win_prob"]
        assert abs(result["combined_prob"] - expected) < 1e-9
