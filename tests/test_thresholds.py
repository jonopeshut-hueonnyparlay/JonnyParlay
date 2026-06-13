"""Sanity tests for structural decision-boundary constants in thresholds.py.

Existence / type / range / locked-value checks. GAME_LINE_KELLY_FRACTION does
not exist in this module and is intentionally not tested.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from thresholds import (
    KELLY_FRACTION,
    POISSON_CUTOFF,
    PLATT_SPACE,
    WNBA_EV_FLOOR,
    KILLSHOT_SIZE_BASE, KILLSHOT_SIZE_BUMP,
    KILLSHOT_WEEKLY_CAP,
    KILLSHOT_ODDS_MIN, KILLSHOT_ODDS_MAX,
    KILLSHOT_SCORE_FLOOR,
    MIN_PICK_SCORE, MIN_WIN_PROB,
    LONGSHOT_SIZE, VALUE_PARLAY_SIZE,
    BLEND_ALPHA, F5_SCALAR,
)


def test_kelly_fraction_positive_float():
    assert isinstance(KELLY_FRACTION, float) and KELLY_FRACTION > 0


def test_poisson_cutoff_positive():
    assert POISSON_CUTOFF > 0


def test_platt_space_is_raw():
    # Locked: prob_core._platt_calibrate_prop asserts this matches its formula space.
    assert PLATT_SPACE == "raw"


def test_wnba_ev_floor_range():
    assert 0.0 < WNBA_EV_FLOOR < 0.5


def test_killshot_sizes():
    assert KILLSHOT_SIZE_BASE > 0
    assert KILLSHOT_SIZE_BUMP > KILLSHOT_SIZE_BASE


def test_killshot_weekly_cap_locked():
    assert KILLSHOT_WEEKLY_CAP == 2


def test_killshot_odds_window():
    assert KILLSHOT_ODDS_MIN < 0
    assert KILLSHOT_ODDS_MAX > 0
    assert KILLSHOT_ODDS_MIN < KILLSHOT_ODDS_MAX


def test_killshot_score_floor_positive():
    assert KILLSHOT_SCORE_FLOOR > 0


def test_min_pick_score_nonnegative():
    assert MIN_PICK_SCORE >= 0


def test_min_win_prob_in_unit_interval():
    assert 0.0 < MIN_WIN_PROB < 1.0


def test_parlay_sizes_positive():
    assert LONGSHOT_SIZE > 0
    assert VALUE_PARLAY_SIZE > 0


def test_blend_alpha_in_unit_interval():
    assert 0.0 < BLEND_ALPHA < 1.0


def test_f5_scalar_sane_range():
    assert 0.4 < F5_SCALAR < 0.7


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
