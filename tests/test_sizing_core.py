"""Tests for sizing_core helpers not already covered elsewhere.

Coverage already provided and intentionally NOT duplicated here:
  - get_market_mult / size_picks_base integration -> tests/test_kelly_market_mult.py
  - apply_bm_shrinkage / get_tier / get_tier_min_edge -> tests/test_plan9_tier_restructure.py

Genuine gaps filled below: kelly_units and round_units.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from sizing_core import kelly_units, round_units
from thresholds import KELLY_FRACTION


# ---------------------------------------------------------------------------
# kelly_units
# ---------------------------------------------------------------------------

def test_kelly_units_positive_when_edge_positive():
    assert kelly_units(0.60, -110) > 0


def test_kelly_units_zero_at_no_edge():
    # win_prob exactly at the implied prob of -110 -> f* = 0 -> 0.0
    from quant.odds import implied_prob
    assert kelly_units(implied_prob(-110), -110) == pytest.approx(0.0, abs=1e-9)


def test_kelly_units_zero_when_below_implied():
    assert kelly_units(0.40, -110) == 0.0


def test_kelly_units_zero_for_even_odds_arg():
    # odds == 0 is treated as no-bet.
    assert kelly_units(0.60, 0) == 0.0


def test_kelly_units_zero_for_invalid_odds():
    assert kelly_units(0.60, "not-a-number") == 0.0


def test_kelly_units_monotone_in_win_prob():
    lo = kelly_units(0.55, -110)
    hi = kelly_units(0.70, -110)
    assert hi >= lo


def test_kelly_units_scales_with_fraction():
    # f* * KELLY_FRACTION: at win_prob 0.60, -110, b = 100/110.
    b = 100.0 / 110.0
    f_star = (b * 0.60 - 0.40) / b
    assert kelly_units(0.60, -110) == pytest.approx(f_star * KELLY_FRACTION)


# ---------------------------------------------------------------------------
# round_units (round to nearest 0.25)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("u", [0.0, 0.1, 0.3, 0.6, 0.9, 1.37, 2.6])
def test_round_units_is_multiple_of_quarter(u):
    out = round_units(u)
    # out is a multiple of 0.25
    assert round(out * 4) == pytest.approx(out * 4)
    assert out == pytest.approx(round(out / 0.25) * 0.25)


def test_round_units_exact_cases():
    # round(u*4)/4 — nearest-quarter rounding. .5 boundaries use banker's
    # rounding and are intentionally avoided here.
    assert round_units(0.0) == 0.0
    assert round_units(0.1) == 0.0
    assert round_units(0.3) == 0.25
    assert round_units(0.6) == 0.50


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
