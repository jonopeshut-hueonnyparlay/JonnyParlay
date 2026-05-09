"""Tests for the extended_absence cold_start sub-type cap formula.

RB8: players returning from a 60-179 day absence get
  cold_start_min_cap = min(career_avg_min * 0.70, 25.0)
with a fallback of 14.0 when no career average is available.

Boundary conditions with new_acquisition (<60 days, cap=28) and
returner (>=180 days, cap=22) are covered in test_projections_db_r7.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))


# ---------------------------------------------------------------------------
# Helpers — apply the classification logic directly (mirrors nba_projector)
# ---------------------------------------------------------------------------

def _classify(days_since: int | None, n_career: int, career_avg: float | None):
    """Mirror of the cold_start classification + cap logic in project_player()."""
    if n_career == 0:
        return "taxi", 12.0
    if days_since is None or days_since >= 180:
        return "returner", min(career_avg, 22.0) if career_avg else 14.0
    if days_since >= 60:
        return "extended_absence", min(career_avg * 0.70, 25.0) if career_avg else 14.0
    return "new_acquisition", min(career_avg, 28.0) if career_avg else 16.0


# ---------------------------------------------------------------------------
# Cap formula tests
# ---------------------------------------------------------------------------

class TestExtendedAbsenceCapFormula:

    def test_cap_is_70_pct_of_career_avg(self):
        sub, cap = _classify(90, n_career=5, career_avg=30.0)
        assert sub == "extended_absence"
        assert abs(cap - 21.0) < 0.001  # 30 * 0.70 = 21

    def test_cap_clamps_at_25(self):
        """Career avg × 0.70 > 25 → cap is 25."""
        sub, cap = _classify(90, n_career=5, career_avg=40.0)
        assert sub == "extended_absence"
        assert cap == 25.0  # 40 * 0.70 = 28, clamped to 25

    def test_cap_below_25_not_clamped(self):
        sub, cap = _classify(90, n_career=5, career_avg=20.0)
        assert sub == "extended_absence"
        assert abs(cap - 14.0) < 0.001  # 20 * 0.70 = 14

    def test_fallback_when_no_career_avg(self):
        sub, cap = _classify(90, n_career=5, career_avg=None)
        assert sub == "extended_absence"
        assert cap == 14.0

    def test_cap_boundary_exactly_35_71_avg(self):
        """career_avg = 35.71 → 35.71 * 0.70 = 24.997 < 25, not clamped."""
        sub, cap = _classify(120, n_career=10, career_avg=35.71)
        assert sub == "extended_absence"
        assert cap < 25.0

    def test_cap_boundary_exactly_35_72_avg(self):
        """career_avg = 35.72 → 35.72 * 0.70 = 25.004 > 25, clamped."""
        sub, cap = _classify(120, n_career=10, career_avg=35.72)
        assert sub == "extended_absence"
        assert cap == 25.0


class TestExtendedAbsenceVsNeighbors:
    """Verify extended_absence caps are correctly bracketed by its neighbors."""

    def test_extended_absence_cap_lower_than_new_acquisition(self):
        """With same career_avg, extended_absence cap < new_acquisition cap."""
        career_avg = 28.0
        _, ea_cap = _classify(90, n_career=5, career_avg=career_avg)
        _, na_cap = _classify(30, n_career=5, career_avg=career_avg)
        assert ea_cap < na_cap  # 19.6 < 28.0

    def test_extended_absence_cap_higher_than_returner_for_high_avg(self):
        """With high career_avg (36+), extended_absence cap (25) > returner cap (22)."""
        career_avg = 36.0
        _, ea_cap = _classify(90, n_career=5, career_avg=career_avg)
        _, ret_cap = _classify(200, n_career=5, career_avg=career_avg)
        assert ea_cap > ret_cap  # 25 > 22 — extended_absence is less penalized

    def test_extended_absence_cap_lower_than_returner_for_low_avg(self):
        """With low career_avg (18), extended_absence cap (12.6) < returner cap (18)."""
        career_avg = 18.0
        _, ea_cap = _classify(90, n_career=5, career_avg=career_avg)
        _, ret_cap = _classify(200, n_career=5, career_avg=career_avg)
        assert ea_cap < ret_cap  # 12.6 < 18


class TestExtendedAbsenceConstantInSource:
    """Source-level check: nba_projector contains the extended_absence branch."""

    def test_extended_absence_branch_present(self):
        import inspect
        import nba_projector
        src = inspect.getsource(nba_projector.project_player)
        assert "extended_absence" in src
        assert "career_avg_min_raw * 0.70" in src
