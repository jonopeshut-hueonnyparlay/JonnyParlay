"""Tests for mlb_sgp_builder.py — R2_MLB kill, rho correction, OUTS win-prob floor."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

import mlb_sgp_builder as mlb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _leg(stat="OUTS", direction="over", game="MIA @ NYM", player="Player A",
         team="MIA", fair_prob=0.68, edge=0.04, odds=-130, book="betmgm",
         line=5.5):
    return {
        "stat":      stat,
        "direction": direction,
        "game":      game,
        "player":    player,
        "team":      team,
        "fair_prob": fair_prob,
        "edge":      edge,
        "odds":      odds,
        "book":      book,
        "line":      line,
        "proj":      line + 1.5,
        "nv_imp":    fair_prob - edge,
        "pool_score": edge,
        "book_odds": {book: odds},
        "is_pitcher": stat == "OUTS",
    }


# ---------------------------------------------------------------------------
# R2_MLB kill rule: OUTS under + HITS under same game
# ---------------------------------------------------------------------------

class TestR2MLBKillRule:
    def test_outs_under_hits_under_same_game_killed(self):
        """R2_MLB fires: OUTS under + HITS under in the same game."""
        pitcher = _leg(stat="OUTS", direction="under", game="MIA @ NYM", player="P1", team="MIA")
        batter  = _leg(stat="HITS", direction="under", game="MIA @ NYM", player="B1", team="NYM")
        assert not mlb._check_parlay_correlations_mlb([pitcher, batter])

    def test_outs_under_hits_under_different_games_allowed(self):
        """R2_MLB does NOT fire when legs are from different games."""
        pitcher = _leg(stat="OUTS", direction="under", game="MIA @ NYM", player="P1", team="MIA")
        batter  = _leg(stat="HITS", direction="under", game="CHC @ LAD", player="B1", team="LAD")
        assert mlb._check_parlay_correlations_mlb([pitcher, batter])

    def test_outs_over_hits_under_not_killed_by_r2(self):
        """R2_MLB does NOT fire on OUTS over + HITS under (different directions — rho handles it)."""
        pitcher = _leg(stat="OUTS", direction="over",  game="MIA @ NYM", player="P1", team="MIA")
        batter  = _leg(stat="HITS", direction="under", game="MIA @ NYM", player="B1", team="NYM")
        # Directions are not both "under" → R2_MLB skips; should pass correlation check
        assert mlb._check_parlay_correlations_mlb([pitcher, batter])

    def test_outs_under_hits_over_not_killed_by_r2(self):
        """R2_MLB does NOT fire on OUTS under + HITS over (only both-under triggers it)."""
        pitcher = _leg(stat="OUTS", direction="under", game="MIA @ NYM", player="P1", team="MIA")
        batter  = _leg(stat="HITS", direction="over",  game="MIA @ NYM", player="B1", team="NYM")
        assert mlb._check_parlay_correlations_mlb([pitcher, batter])


# ---------------------------------------------------------------------------
# Rho correction: OUTS over + opposing HITS under → 0.30
# ---------------------------------------------------------------------------

class TestPairwiseRhoMLB:
    def test_outs_over_hits_under_opposing_rho_0_30(self):
        """OUTS over (pitcher) + HITS under (opposing batter) → rho = 0.30."""
        pitcher = _leg(stat="OUTS", direction="over",  team="MIA", game="MIA @ NYM")
        batter  = _leg(stat="HITS", direction="under", team="NYM", game="MIA @ NYM")
        assert mlb._pairwise_rho_mlb(pitcher, batter) == 0.30

    def test_outs_over_hits_under_opposing_rho_0_30_reversed(self):
        """Argument order reversed — still 0.30."""
        pitcher = _leg(stat="OUTS", direction="over",  team="MIA", game="MIA @ NYM")
        batter  = _leg(stat="HITS", direction="under", team="NYM", game="MIA @ NYM")
        assert mlb._pairwise_rho_mlb(batter, pitcher) == 0.30

    def test_outs_under_hits_under_fallback_rho_0_02(self):
        """OUTS under + HITS under — does NOT match the 0.30 case → 0.02 fallback."""
        pitcher = _leg(stat="OUTS", direction="under", team="MIA")
        batter  = _leg(stat="HITS", direction="under", team="NYM")
        assert mlb._pairwise_rho_mlb(pitcher, batter) == 0.02

    def test_outs_over_hits_over_fallback_rho_0_02(self):
        """OUTS over + HITS over — both over, opposing teams → 0.02 fallback."""
        pitcher = _leg(stat="OUTS", direction="over", team="MIA")
        batter  = _leg(stat="HITS", direction="over", team="NYM")
        assert mlb._pairwise_rho_mlb(pitcher, batter) == 0.02

    def test_same_team_outs_over_hits_under_fallback_rho_0_02(self):
        """OUTS over + HITS under but same team — 0.30 does NOT apply → 0.02 fallback."""
        pitcher = _leg(stat="OUTS", direction="over",  team="MIA")
        batter  = _leg(stat="HITS", direction="under", team="MIA")
        assert mlb._pairwise_rho_mlb(pitcher, batter) == 0.02

    def test_generic_pitcher_batter_fallback_unchanged(self):
        """OUTS under + HITS over (generic mismatch) → 0.02 fallback unchanged."""
        pitcher = _leg(stat="OUTS", direction="under", team="MIA")
        batter  = _leg(stat="HITS", direction="over",  team="NYM")
        assert mlb._pairwise_rho_mlb(pitcher, batter) == 0.02


# ---------------------------------------------------------------------------
# OUTS win-prob floor: MIN_LEG_WIN_PROB_OUTS = 0.62
# ---------------------------------------------------------------------------

class TestOUTSWinProbFloor:
    def test_min_leg_win_prob_outs_constant(self):
        """New OUTS-specific floor constant exists and equals 0.62."""
        assert mlb.MIN_LEG_WIN_PROB_OUTS == 0.62

    def test_global_floor_unchanged(self):
        """Global floor remains 0.65 — OUTS floor does not affect it."""
        assert mlb.MIN_LEG_WIN_PROB == 0.65

    def test_outs_floor_is_lower_than_global(self):
        """OUTS floor is strictly lower than the global floor."""
        assert mlb.MIN_LEG_WIN_PROB_OUTS < mlb.MIN_LEG_WIN_PROB
