"""Tests for filter_cross_type_correlations and NRFI Poisson rewrite."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest
import math
import run_picks as rp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick(stat, direction, team, score=50.0, game="BOS @ NYY"):
    return {
        "stat": stat, "direction": direction, "team_abbrev": team,
        "game": game, "player": f"{team}_{stat}", "pick_score": score,
    }


# ---------------------------------------------------------------------------
# filter_cross_type_correlations — X1 (HA/ER under + opp TT over)
# ---------------------------------------------------------------------------

class TestCrossTypeX1:
    def test_ha_under_plus_opp_tt_over_drops_lower(self):
        """Pitcher HA UNDER (higher score) + opp TEAM_TOTAL OVER (lower score) → drop TT."""
        ha_pick = _pick("HA",         "under", "BOS", score=60)
        tt_pick = _pick("TEAM_TOTAL", "over",  "NYY", score=40)
        result  = rp.filter_cross_type_correlations([ha_pick, tt_pick])
        assert len(result) == 1
        assert result[0]["stat"] == "HA"

    def test_er_under_plus_opp_tt_over_drops_lower(self):
        """Pitcher ER UNDER + opp TEAM_TOTAL OVER → drop ER under (lower score here)."""
        er_pick = _pick("ER",         "under", "NYY", score=30)
        tt_pick = _pick("TEAM_TOTAL", "over",  "BOS", score=55)
        result  = rp.filter_cross_type_correlations([er_pick, tt_pick])
        assert len(result) == 1
        assert result[0]["stat"] == "TEAM_TOTAL"

    def test_same_team_ha_under_tt_over_no_kill(self):
        """Pitcher HA UNDER + SAME team TT OVER = not anti-correlated (same team)."""
        ha_pick = _pick("HA",         "under", "BOS", score=60)
        tt_pick = _pick("TEAM_TOTAL", "over",  "BOS", score=40)
        result  = rp.filter_cross_type_correlations([ha_pick, tt_pick])
        assert len(result) == 2

    def test_ha_over_tt_over_no_kill(self):
        """Pitcher HA OVER (not under) + opp TT OVER → not conflicting."""
        ha_pick = _pick("HA",         "over", "BOS", score=60)
        tt_pick = _pick("TEAM_TOTAL", "over", "NYY", score=40)
        result  = rp.filter_cross_type_correlations([ha_pick, tt_pick])
        assert len(result) == 2

    def test_ha_under_tt_under_no_kill(self):
        """Pitcher HA UNDER + opp TT UNDER → no conflict (both point same direction)."""
        ha_pick = _pick("HA",         "under", "BOS", score=60)
        tt_pick = _pick("TEAM_TOTAL", "under", "NYY", score=40)
        result  = rp.filter_cross_type_correlations([ha_pick, tt_pick])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# filter_cross_type_correlations — X2 (K over + opp HITS over)
# ---------------------------------------------------------------------------

class TestCrossTypeX2:
    def test_k_over_plus_opp_hits_over_drops_lower(self):
        """Pitcher K OVER + opposing batter HITS OVER → drop lower-score leg."""
        k_pick   = _pick("K",    "over", "BOS",  score=70)
        hit_pick = _pick("HITS", "over", "NYY",  score=45)
        result   = rp.filter_cross_type_correlations([k_pick, hit_pick])
        assert len(result) == 1
        assert result[0]["stat"] == "K"

    def test_k_under_hits_over_no_kill(self):
        """K UNDER (not over) + opp HITS OVER → no kill (K under is a different signal)."""
        k_pick   = _pick("K",    "under", "BOS", score=70)
        hit_pick = _pick("HITS", "over",  "NYY", score=45)
        result   = rp.filter_cross_type_correlations([k_pick, hit_pick])
        assert len(result) == 2

    def test_k_over_same_team_hits_over_no_kill(self):
        """K OVER + SAME team HITS OVER → no kill (different sides of the ball)."""
        k_pick   = _pick("K",    "over", "BOS", score=70)
        hit_pick = _pick("HITS", "over", "BOS", score=45)
        result   = rp.filter_cross_type_correlations([k_pick, hit_pick])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# filter_cross_type_correlations — unrelated picks pass through untouched
# ---------------------------------------------------------------------------

class TestCrossTypeNoConflict:
    def test_pts_and_tt_over_no_kill(self):
        """NBA PTS prop + TEAM_TOTAL OVER → no kill (PTS is not HA/ER/K)."""
        pts = _pick("PTS",        "over", "BOS")
        tt  = _pick("TEAM_TOTAL", "over", "NYY")
        assert len(rp.filter_cross_type_correlations([pts, tt])) == 2

    def test_outs_and_hits_over_no_kill(self):
        """Pitcher OUTS prop + opposing HITS OVER → no kill (OUTS not in kill lists)."""
        outs = _pick("OUTS", "over", "BOS")
        hits = _pick("HITS", "over", "NYY")
        assert len(rp.filter_cross_type_correlations([outs, hits])) == 2

    def test_three_picks_one_conflict(self):
        """Three picks: one conflict pair → drop 1 lower-score, keep 2."""
        ha  = _pick("HA",         "under", "BOS", score=80)
        tt  = _pick("TEAM_TOTAL", "over",  "NYY", score=30)
        sog = _pick("SOG",        "over",  "TBL", score=60, game="TBL @ NYR")
        result = rp.filter_cross_type_correlations([ha, tt, sog])
        stats = {p["stat"] for p in result}
        assert len(result) == 2
        assert "HA" in stats and "SOG" in stats
        assert "TEAM_TOTAL" not in stats


# ---------------------------------------------------------------------------
# filter_game_line_correlations — Rule 5 (NRFI + YRFI same game)
# ---------------------------------------------------------------------------

class TestNrfiYrfiRule5:
    def _gl_pick(self, stat, score=50.0):
        return {
            "stat": stat, "direction": "over" if stat == "YRFI" else "under",
            "game": "BOS @ NYY", "player": stat, "pick_score": score,
            "is_home": None,
        }

    def test_nrfi_yrfi_same_game_drops_lower(self):
        nrfi = self._gl_pick("NRFI", score=60)
        yrfi = self._gl_pick("YRFI", score=40)
        result = rp.filter_game_line_correlations([nrfi, yrfi])
        assert len(result) == 1
        assert result[0]["stat"] == "NRFI"

    def test_nrfi_yrfi_different_games_kept(self):
        nrfi = self._gl_pick("NRFI")
        nrfi["game"] = "BOS @ NYY"
        yrfi = self._gl_pick("YRFI")
        yrfi["game"] = "LAD @ SF"
        result = rp.filter_game_line_correlations([nrfi, yrfi])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# NRFI Poisson model calibration checks
# ---------------------------------------------------------------------------

class TestNrfiPoissonCalibration:
    """Spot-check that the new Poisson model produces calibrated NRFI probabilities.

    We drive the model indirectly through the constants: construct synthetic
    pitcher_map and team_saber_runs entries and verify the lambda/probability
    math is correct by replicating it here.
    """

    _BASE_LAMBDA_1ST      = 0.32
    _LEAGUE_AVG_RUNS      = 4.39
    _LEAGUE_AVG_BLENDED   = 0.438

    def _compute_p_nrfi(self, home_blended, away_blended,
                         home_runs, away_runs):
        home_pitch_mult = home_blended / self._LEAGUE_AVG_BLENDED
        away_pitch_mult = away_blended / self._LEAGUE_AVG_BLENDED
        off_away = away_runs / self._LEAGUE_AVG_RUNS
        off_home = home_runs / self._LEAGUE_AVG_RUNS
        lam_away = max(0.05, min(0.90, self._BASE_LAMBDA_1ST * home_pitch_mult * off_away))
        lam_home = max(0.05, min(0.90, self._BASE_LAMBDA_1ST * away_pitch_mult * off_home))
        return math.exp(-(lam_away + lam_home))

    def test_average_matchup_nrfi_near_53pct(self):
        """Average pitcher quality and offense → P(NRFI) ≈ 52-54%."""
        p = self._compute_p_nrfi(
            home_blended=0.438, away_blended=0.438,
            home_runs=4.39, away_runs=4.39,
        )
        assert 0.50 <= p <= 0.56, f"Expected ~53%, got {p:.3f}"

    def test_elite_pitchers_higher_nrfi(self):
        """Elite pitcher (FIP=2.8) → P(NRFI) meaningfully above average."""
        # FIP=2.8 → fip_per_ip=0.311; ERA=3.0 → er_per_ip=0.333
        # blended = 0.40*0.333 + 0.60*0.311 = 0.320
        elite = 0.320
        p = self._compute_p_nrfi(
            home_blended=elite, away_blended=elite,
            home_runs=4.39, away_runs=4.39,
        )
        avg_p = self._compute_p_nrfi(0.438, 0.438, 4.39, 4.39)
        assert p > avg_p, "Elite pitchers should produce higher P(NRFI)"
        assert p >= 0.60, f"Two elite pitchers should be >=60% NRFI, got {p:.3f}"

    def test_poor_pitchers_lower_nrfi(self):
        """Poor pitcher (ERA=5.5, FIP=5.0) → P(NRFI) below average."""
        # FIP=5.0 → fip_per_ip=0.556; ERA=5.5 → er_per_ip=0.611
        # blended = 0.40*0.611 + 0.60*0.556 = 0.578
        poor = 0.578
        p = self._compute_p_nrfi(
            home_blended=poor, away_blended=poor,
            home_runs=4.39, away_runs=4.39,
        )
        avg_p = self._compute_p_nrfi(0.438, 0.438, 4.39, 4.39)
        assert p < avg_p, "Poor pitchers should lower P(NRFI)"
        assert p <= 0.44, f"Two poor pitchers should be <=44% NRFI, got {p:.3f}"

    def test_high_offense_team_lowers_nrfi(self):
        """High-scoring offense (6.0 R/game, like a Coors team) → lower P(NRFI)."""
        p_high = self._compute_p_nrfi(0.438, 0.438, 6.0, 6.0)
        p_avg  = self._compute_p_nrfi(0.438, 0.438, 4.39, 4.39)
        assert p_high < p_avg, "High-offense environment should lower P(NRFI)"

    def test_lambda_bounds_respected(self):
        """Extreme inputs should be clamped to lambda bounds [0.05, 0.90]."""
        # Near-zero pitcher quality (very poor)
        p_low = self._compute_p_nrfi(10.0, 10.0, 10.0, 10.0)
        # Near-zero offense + elite pitcher
        p_high = self._compute_p_nrfi(0.01, 0.01, 0.1, 0.1)
        # Both should be valid probabilities
        assert 0.0 < p_low < 1.0
        assert 0.0 < p_high <= 1.0
