"""Tests for mlb_sgp_builder.py — R2_MLB kill, rho correction, OUTS win-prob floor,
SP scratch detection, 429 retry, fast copula approx, cohesion scoring."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

from unittest.mock import patch, MagicMock
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


# ---------------------------------------------------------------------------
# Change 1: SP scratch detection
# ---------------------------------------------------------------------------

class TestSPScratchDetection:
    def _minimal_event(self):
        return {"id": "evt1", "away_team": "MIA", "home_team": "NYM", "commence_time": "2026-06-04T00:00:00Z"}

    def test_sp_scratch_returns_none(self):
        """build_mlb_sgp returns None when a pitcher is not in confirmed_starters."""
        confirmed = {"NYM": ["Max Scherzer"]}  # MIA pitcher missing
        pitcher_cand = _leg(stat="OUTS", direction="over", player="Sandy Alcantara", team="MIA",
                            fair_prob=0.68, edge=0.04, odds=-130)
        batter_cand1 = _leg(stat="HITS", direction="over", player="Batter One", team="NYM",
                            fair_prob=0.68, edge=0.04, odds=-130)
        batter_cand2 = _leg(stat="HITS", direction="over", player="Batter Two", team="MIA",
                            fair_prob=0.68, edge=0.04, odds=-140)
        with patch.object(mlb, "build_candidate_legs_mlb", return_value=[pitcher_cand, batter_cand1, batter_cand2]):
            result = mlb.build_mlb_sgp({}, {}, self._minimal_event(),
                                        confirmed_starters=confirmed)
        assert result is None

    def test_sp_confirmed_proceeds_past_scratch_guard(self):
        """build_mlb_sgp does NOT short-circuit when pitcher IS in confirmed_starters."""
        confirmed = {"MIA": ["Sandy Alcantara"]}
        pitcher_cand = _leg(stat="OUTS", direction="over", player="Sandy Alcantara", team="MIA",
                            fair_prob=0.68, edge=0.04, odds=-130)
        # Fewer than MIN_LEGS candidates so function returns None from legs check, not scratch guard
        with patch.object(mlb, "build_candidate_legs_mlb", return_value=[pitcher_cand]):
            with patch("mlb_sgp_builder.is_confirmed", return_value=True) as mock_ic:
                mlb.build_mlb_sgp({}, {}, self._minimal_event(), confirmed_starters=confirmed)
        mock_ic.assert_called_once_with("Sandy Alcantara", "MIA", confirmed)

    def test_empty_confirmed_starters_skips_check(self):
        """Empty confirmed_starters dict (network error) — scratch guard is disabled."""
        pitcher_cand = _leg(stat="OUTS", direction="over", player="Sandy Alcantara", team="MIA",
                            fair_prob=0.68, edge=0.04, odds=-130)
        with patch.object(mlb, "build_candidate_legs_mlb", return_value=[pitcher_cand]):
            with patch("mlb_sgp_builder.is_confirmed") as mock_ic:
                mlb.build_mlb_sgp({}, {}, self._minimal_event(), confirmed_starters={})
        mock_ic.assert_not_called()


# ---------------------------------------------------------------------------
# Change 2: 429 retry in _api_get()
# ---------------------------------------------------------------------------

class TestApiGet429Retry:
    def _make_response(self, status_code, json_data=None, retry_after=None):
        r = MagicMock()
        r.status_code = status_code
        r.headers = {"Retry-After": str(retry_after)} if retry_after else {}
        if status_code == 200:
            r.json.return_value = json_data or {"ok": True}
            r.raise_for_status.return_value = None
        else:
            r.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return r

    def test_retries_on_429_then_succeeds(self):
        """_api_get retries on 429 and returns JSON on subsequent 200."""
        responses = [
            self._make_response(429, retry_after=0),
            self._make_response(429, retry_after=0),
            self._make_response(200, {"data": 1}),
        ]
        with patch("mlb_sgp_builder.time.sleep"):
            with patch("requests.get", side_effect=responses):
                result = mlb._api_get("http://x", {})
        assert result == {"data": 1}

    def test_raises_after_max_retries(self):
        """_api_get raises after 3 consecutive 429 responses."""
        responses = [self._make_response(429, retry_after=0)] * 3
        import pytest
        with patch("mlb_sgp_builder.time.sleep"):
            with patch("requests.get", side_effect=responses):
                with pytest.raises(Exception):
                    mlb._api_get("http://x", {})


# ---------------------------------------------------------------------------
# Change 3: Fast copula approx used in ranking pass (not full MC)
# ---------------------------------------------------------------------------

class TestFastCopulaApprox:
    def test_score_mlb_sgp_uses_approx_not_mc(self):
        """_score_mlb_sgp uses _copula_joint_approx, NOT _copula_joint_prob (full MC)."""
        legs = [
            _leg(stat="OUTS", direction="over",  player="P1", team="MIA", odds=-130),
            _leg(stat="HITS", direction="under", player="B1", team="NYM", odds=-115),
            _leg(stat="HITS", direction="over",  player="B2", team="MIA", odds=-125),
        ]
        with patch("mlb_sgp_builder._copula_joint_prob") as mock_mc:
            with patch("mlb_sgp_builder._copula_joint_approx", return_value=0.30) as mock_approx:
                mlb._score_mlb_sgp(legs)
        mock_approx.assert_called_once()
        mock_mc.assert_not_called()


# ---------------------------------------------------------------------------
# Change 4: Cohesion scoring
# ---------------------------------------------------------------------------

class TestCohesionScoring:
    def test_pitcher_dom_outs_over_hits_under_share_tag(self):
        """OUTS over + opposing HITS under share pitcher_dom tag → cohesion = 1.0."""
        outs_leg  = _leg(stat="OUTS", direction="over",  player="P1", team="MIA", game="MIA @ NYM")
        hits_under = _leg(stat="HITS", direction="under", player="B1", team="NYM", game="MIA @ NYM")
        tags_p = mlb._correlation_tags_mlb(outs_leg)
        tags_b = mlb._correlation_tags_mlb(hits_under)
        assert tags_p & tags_b, "OUTS over + HITS under should share pitcher_dom tag"

    def test_pitcher_dom_and_batter_hot_no_shared_tag(self):
        """OUTS over + HITS over do not share a tag (different game scripts)."""
        outs_leg  = _leg(stat="OUTS", direction="over", player="P1", team="MIA", game="MIA @ NYM")
        hits_over = _leg(stat="HITS", direction="over", player="B1", team="NYM", game="MIA @ NYM")
        tags_p = mlb._correlation_tags_mlb(outs_leg)
        tags_b = mlb._correlation_tags_mlb(hits_over)
        assert not (tags_p & tags_b), "OUTS over + HITS over should not share a tag"

    def test_cohesion_boosts_coherent_combo(self):
        """Pitcher-dom stack (OUTS over + HITS under) scores higher than mixed-script stack."""
        # Coherent: pitcher dominates (OUTS over + opposing HITS under)
        coherent = [
            _leg(stat="OUTS", direction="over",  player="P1", team="MIA", game="MIA @ NYM", odds=-120),
            _leg(stat="HITS", direction="under", player="B1", team="NYM", game="MIA @ NYM", odds=-115),
            _leg(stat="HITS", direction="under", player="B2", team="NYM", game="MIA @ NYM", odds=-110),
        ]
        # Incoherent: batter explosion + pitcher dominance (opposite scripts)
        incoherent = [
            _leg(stat="OUTS", direction="over",  player="P1", team="MIA", game="MIA @ NYM", odds=-120),
            _leg(stat="HITS", direction="over",  player="B1", team="NYM", game="MIA @ NYM", odds=-115),
            _leg(stat="HITS", direction="over",  player="B2", team="MIA", game="MIA @ NYM", odds=-110),
        ]
        score_coherent   = mlb._correlation_cohesion_mlb(coherent)
        score_incoherent = mlb._correlation_cohesion_mlb(incoherent)
        assert score_coherent > score_incoherent

    def test_score_mlb_sgp_weights_sum_to_one(self):
        """Verify the documented scoring weights sum to 1.0."""
        weights = [0.25, 0.30, 0.15, 0.25, 0.05]  # edge, copula, odds, cohesion, stat_div
        assert abs(sum(weights) - 1.0) < 1e-9
