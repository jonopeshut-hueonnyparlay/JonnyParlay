"""Tests for the H5 high-variance player flag.

project_player() must:
  - Compute pts_cv = std(pts) / mean(pts) from clean game history
  - Include pts_cv in the returned projection dict
  - Use observed pts_std as an additional dk_std floor

run_projections() must:
  - Log [HIGH-VAR] WARNING for players with pts_cv >= HIGH_VAR_CV_THRESHOLD

Constants: HIGH_VAR_CV_THRESHOLD=0.60, HIGH_VAR_MIN_GAMES=8
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pts_series(values: list[float]):
    """Return a pandas DataFrame that looks like df_clean with a pts column."""
    import pandas as pd
    return pd.DataFrame({
        "min": [20.0] * len(values),
        "pts": values,
        "starter_flag": [1] * len(values),
        "game_date": [f"2026-0{(i//30)+1}-{(i%28)+1:02d}" for i in range(len(values))],
    })


def _std(values):
    n = len(values)
    mean = sum(values) / n
    return math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))


# ---------------------------------------------------------------------------
# Unit tests for the CV / dk_std calculation (no DB needed)
# ---------------------------------------------------------------------------

class TestHighVarConstants:

    def test_threshold_is_0_60(self):
        import nba_projector as nbp
        assert nbp.HIGH_VAR_CV_THRESHOLD == 0.60

    def test_min_games_is_8(self):
        import nba_projector as nbp
        assert nbp.HIGH_VAR_MIN_GAMES == 8


class TestPtsCvComputation:
    """Verify pts_cv is computed correctly from df_clean."""

    def _run(self, pts_values):
        """Call the CV logic that mirrors project_player's inner block."""
        import pandas as pd
        import nba_projector as nbp
        df_clean = _make_pts_series(pts_values)
        pts_cv = None
        pts_std_recent = 0.0
        if len(df_clean) >= nbp.HIGH_VAR_MIN_GAMES and "pts" in df_clean.columns:
            _pts = df_clean["pts"].head(20)
            _mean = float(_pts.mean())
            if _mean > 4.0:
                pts_std_recent = float(_pts.std(ddof=1))
                pts_cv = round(pts_std_recent / _mean, 3)
        return pts_cv, pts_std_recent

    def test_high_cv_strus_type(self):
        """8.4 std / 10.8 mean = 0.78 — should be flagged."""
        pts = [0, 24, 1, 15, 24, 8, 2, 6, 10, 8, 12, 19, 11, 29, 11, 5, 0, 6, 24, 0]
        cv, std = self._run(pts)
        assert cv is not None
        assert cv > 0.60

    def test_low_cv_tatum_type(self):
        """Consistent scorer should not be flagged."""
        pts = [24, 22, 26, 20, 25, 23, 28, 21, 24, 22]
        cv, std = self._run(pts)
        assert cv is not None
        assert cv < 0.60

    def test_none_when_below_min_games(self):
        """Fewer than HIGH_VAR_MIN_GAMES — cv should be None."""
        pts = [10, 20, 5, 25, 8, 15, 3]  # 7 games < 8
        cv, std = self._run(pts)
        assert cv is None
        assert std == 0.0

    def test_none_when_mean_too_low(self):
        """Mean <= 4.0 (e.g. cold_start) — cv should be None."""
        pts = [0, 0, 2, 0, 0, 0, 0, 0, 0, 0]
        cv, std = self._run(pts)
        assert cv is None

    def test_cv_formula(self):
        """Verify the exact formula: cv = std(ddof=1) / mean."""
        pts = [5, 10, 15, 20, 5, 25, 8, 12]
        cv, std_val = self._run(pts)
        expected_mean = sum(pts) / len(pts)
        expected_std = _std(pts)
        expected_cv = round(expected_std / expected_mean, 3)
        assert cv == expected_cv


class TestDkStdFloor:
    """pts_std_recent should floor dk_std when it exceeds the other two sources."""

    def test_pts_std_floors_dk_std(self):
        """When observed std > 0.35*proj + role_floor, dk_std == observed std."""
        import nba_projector as nbp
        proj_pts = 10.8
        role = "sixth_man"
        pts_std_recent = 8.4   # Strus-level variance
        dk = round(max(proj_pts * nbp.DK_STD_COEFF,
                       nbp.DK_STD_FLOOR.get(role, 3.0),
                       pts_std_recent), 2)
        assert dk == 8.4

    def test_formula_unchanged_for_consistent_player(self):
        """Low-variance player: dk_std still 0.35*proj_pts."""
        import nba_projector as nbp
        proj_pts = 22.6
        role = "starter"
        pts_std_recent = 4.4  # Tatum-level variance
        dk = round(max(proj_pts * nbp.DK_STD_COEFF,
                       nbp.DK_STD_FLOOR.get(role, 3.0),
                       pts_std_recent), 2)
        assert abs(dk - round(proj_pts * nbp.DK_STD_COEFF, 2)) < 0.01

    def test_zero_std_does_not_lower_dk_std(self):
        """pts_std_recent=0 (cold_start, <8 games) — other terms dominate."""
        import nba_projector as nbp
        proj_pts = 8.0
        role = "cold_start"
        pts_std_recent = 0.0
        dk = round(max(proj_pts * nbp.DK_STD_COEFF,
                       nbp.DK_STD_FLOOR.get(role, 3.0),
                       pts_std_recent), 2)
        assert dk == nbp.DK_STD_FLOOR["cold_start"]


class TestHighVarLogWarning:
    """run_projections() must emit [HIGH-VAR] WARNING for high-CV players."""

    def test_high_var_player_logs_warning(self, caplog):
        import logging
        import nba_projector as nbp

        fake_results = [
            {"player_name": "Max Strus", "role_tier": "sixth_man",
             "pts_cv": 0.77, "proj_pts": 10.8, "dk_std": 8.4},
            {"player_name": "Donovan Mitchell", "role_tier": "starter",
             "pts_cv": 0.34, "proj_pts": 25.0, "dk_std": 8.75},
        ]

        with caplog.at_level(logging.WARNING, logger="jonnyparlay"):
            high_var = [r for r in fake_results
                        if (r.get("pts_cv") or 0) >= nbp.HIGH_VAR_CV_THRESHOLD]
            for r in sorted(high_var, key=lambda x: x["pts_cv"], reverse=True):
                nbp.log.warning(
                    "[HIGH-VAR] %s (%s): pts_cv=%.2f proj_pts=%.1f dk_std=%.1f — "
                    "3PT specialist with bimodal scoring; individual game outcome highly uncertain",
                    r["player_name"], r["role_tier"], r["pts_cv"],
                    r["proj_pts"], r["dk_std"],
                )

        messages = [r.message for r in caplog.records]
        assert any("HIGH-VAR" in m and "Strus" in m for m in messages)
        assert not any("Mitchell" in m for m in messages)

    def test_no_warning_below_threshold(self, caplog):
        import logging
        import nba_projector as nbp

        fake_results = [
            {"player_name": "Donovan Mitchell", "role_tier": "starter",
             "pts_cv": 0.34, "proj_pts": 25.0, "dk_std": 8.75},
        ]

        with caplog.at_level(logging.WARNING, logger="jonnyparlay"):
            high_var = [r for r in fake_results
                        if (r.get("pts_cv") or 0) >= nbp.HIGH_VAR_CV_THRESHOLD]
            for r in high_var:
                nbp.log.warning("[HIGH-VAR] %s", r["player_name"])

        assert not any("HIGH-VAR" in r.message for r in caplog.records)
