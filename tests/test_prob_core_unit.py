"""Unit tests for prob_core functions not covered by routing tests.

WNBA distribution routing for calc_prop_prob is covered by
tests/test_wnba_distribution_routing.py; pick_score tier-neutrality is covered
by tests/test_plan9_tier_restructure.py. Here we fill: Platt calibration bounds
+ space assertion, pick_score mode/cold-start/injury behavior, and non-WNBA
calc_prop_prob / calc_combo_prob output contracts.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from prob_core import (
    _platt_calibrate_prop, calc_prop_prob, calc_combo_prob, pick_score,
)


# ---------------------------------------------------------------------------
# _platt_calibrate_prop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("p", [0.05, 0.2, 0.5, 0.666, 0.9])
def test_platt_output_in_unit_interval(p):
    out = _platt_calibrate_prop(p)
    assert 0.0 < out < 1.0


def test_platt_asserts_raw_space():
    # The formula is raw-probability space; a mismatched PLATT_SPACE must trip
    # the safeguard assertion (assertions are active under the pytest gate).
    with mock.patch("prob_core.PLATT_SPACE", "logit"):
        with pytest.raises(AssertionError):
            _platt_calibrate_prop(0.55)


# ---------------------------------------------------------------------------
# pick_score
# ---------------------------------------------------------------------------

def test_pick_score_nonnegative():
    assert pick_score(0.62, 0.08) >= 0


def test_pick_score_monotone():
    assert pick_score(0.70, 0.15) > pick_score(0.60, 0.10)


def test_pick_score_modes_differ():
    s_def = pick_score(0.62, 0.08, mode="Default")
    s_con = pick_score(0.62, 0.08, mode="Conservative")
    s_agg = pick_score(0.62, 0.08, mode="Aggressive")
    assert s_def != s_con
    assert s_def != s_agg
    assert s_con != s_agg


def test_pick_score_cold_start_lowers():
    base = pick_score(0.62, 0.08)
    chilled = pick_score(0.62, 0.08, cold_start_subtype="taxi")
    assert chilled < base


def test_pick_score_injury_trigger_raises():
    base = pick_score(0.62, 0.08, injury_trigger=False)
    bumped = pick_score(0.62, 0.08, injury_trigger=True)
    assert bumped > base


# ---------------------------------------------------------------------------
# calc_prop_prob (non-WNBA)
# ---------------------------------------------------------------------------

def test_calc_prop_prob_pts_complementary_and_bounded():
    over_p, under_p = calc_prop_prob(30.0, 25.5, "PTS", sport="NBA")
    assert over_p + under_p == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= over_p <= 1.0
    assert 0.0 <= under_p <= 1.0


def test_calc_prop_prob_ast_nb_path_bounded():
    over_p, under_p = calc_prop_prob(8.0, 6.5, "AST", sport="NBA")
    assert over_p + under_p == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= over_p <= 1.0


# ---------------------------------------------------------------------------
# calc_combo_prob
# ---------------------------------------------------------------------------

def test_calc_combo_prob_bounded_and_complementary():
    proj_player = {"PTS": 30.0, "REB": 8.0, "AST": 6.0}
    over_p, under_p = calc_combo_prob(proj_player, "PRA", 40.0, sport="NBA")
    assert 0.0 < over_p < 1.0
    assert over_p + under_p == pytest.approx(1.0, abs=1e-9)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
