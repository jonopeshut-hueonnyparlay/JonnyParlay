"""Sanity tests for fitted constants in calibrated.py.

Existence / type / range / locked-value checks only. Tier-routing structure
(STAT_FAMILY_TIER, TIERS floors, BM_SHRINKAGE_WEIGHT covers-all-tiers /
0<w<=1) is already covered by tests/test_plan9_tier_restructure.py and is NOT
duplicated here. F5_SCALAR and BLEND_ALPHA live in thresholds.py, not
calibrated.py — they are tested in tests/test_thresholds.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from calibrated import (
    PLATT_A, PLATT_B,
    SIGMA, SIGMA_WNBA,
    NB_R, NB_R_WNBA,
    GAME_SIGMA, F5_SIGMA,
    MLB_TEAM_RUN_R,
    KELLY_MARKET_MULT,
    BM_SHRINKAGE_WEIGHT,
    _TEAM_SIGMAS, _TEAM_SIGMAS_MEANSQ,
)


# ---------------------------------------------------------------------------
# Platt
# ---------------------------------------------------------------------------

def test_platt_a_positive_float():
    assert isinstance(PLATT_A, float) and PLATT_A > 0


def test_platt_b_float():
    assert isinstance(PLATT_B, float)  # negative is valid


# ---------------------------------------------------------------------------
# SIGMA tables
# ---------------------------------------------------------------------------

def test_sigma_values_positive():
    for stat, s in SIGMA.items():
        assert s["mult"] > 0, f"SIGMA[{stat}].mult"
        assert s["min"] > 0, f"SIGMA[{stat}].min"


def test_sigma_has_required_keys():
    # PTS/AST/REB are the Normal/combo-path stats. 3PM/SOG are NB/Poisson —
    # intentionally absent from SIGMA.
    assert {"PTS", "AST", "REB"} <= set(SIGMA)


def test_sigma_wnba_values_positive():
    for stat, s in SIGMA_WNBA.items():
        assert s["mult"] > 0 and s["min"] > 0, f"SIGMA_WNBA[{stat}]"


# ---------------------------------------------------------------------------
# Negative-binomial dispersion
# ---------------------------------------------------------------------------

def test_nb_r_values_positive():
    for stat, r in NB_R.items():
        assert r > 0, f"NB_R[{stat}]"


def test_nb_r_has_refitted_keys():
    assert {"AST", "REB"} <= set(NB_R)


def test_nb_r_locked_values():
    # P1.3 2026-06-16: bias-corrected (Jensen MoM) from EdgeModel producer
    # (was 12.16/14.7 from the inflating pooled formula).
    assert NB_R["AST"] == pytest.approx(9.66)
    assert NB_R["REB"] == pytest.approx(13.16)


def test_nb_r_wnba_values_positive():
    assert NB_R_WNBA  # non-empty
    for stat, r in NB_R_WNBA.items():
        assert r > 0, f"NB_R_WNBA[{stat}]"


# ---------------------------------------------------------------------------
# Game-line sigmas
# ---------------------------------------------------------------------------

def test_game_sigma_all_positive():
    for sport, markets in GAME_SIGMA.items():
        for market, v in markets.items():
            assert v > 0, f"GAME_SIGMA[{sport}][{market}]"


def test_game_sigma_locked_values():
    assert GAME_SIGMA["NBA"]["total"] == pytest.approx(18.5)
    assert GAME_SIGMA["WNBA"]["total"] == pytest.approx(17.424)


def test_f5_sigma_all_positive():
    for market, v in F5_SIGMA.items():
        assert v > 0, f"F5_SIGMA[{market}]"


def test_mlb_team_run_r_positive():
    assert MLB_TEAM_RUN_R > 0


# ---------------------------------------------------------------------------
# Kelly market multipliers
# ---------------------------------------------------------------------------

def test_kelly_market_mult_in_unit_interval():
    for key, v in KELLY_MARKET_MULT.items():
        assert 0.0 < v <= 1.0, f"KELLY_MARKET_MULT[{key}]={v}"


# ---------------------------------------------------------------------------
# Baker-McHale weights (locked T2 value only; structure covered by plan9)
# ---------------------------------------------------------------------------

def test_bm_weights_in_unit_interval():
    for tier, w in BM_SHRINKAGE_WEIGHT.items():
        assert 0.0 < w <= 1.0, f"BM_SHRINKAGE_WEIGHT[{tier}]"


def test_bm_weight_t2_locked():
    assert BM_SHRINKAGE_WEIGHT["T2"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Team-sigma tables (loaded from JSON at import)
# ---------------------------------------------------------------------------

def test_team_sigmas_non_empty_dicts():
    assert isinstance(_TEAM_SIGMAS, dict) and _TEAM_SIGMAS
    assert isinstance(_TEAM_SIGMAS_MEANSQ, dict) and _TEAM_SIGMAS_MEANSQ


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
