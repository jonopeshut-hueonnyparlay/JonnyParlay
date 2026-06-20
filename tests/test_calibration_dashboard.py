"""Tests for the calibration drift dashboard (audit S4d-X).

Covers the pure binning/grouping logic (the reader/CLI are thin and exercised by
load_rows' own tests). engine/ is on sys.path via the repo-root conftest, so the
engine/tools package imports directly.
"""

from __future__ import annotations

import pytest

from tools.calibration_dashboard import bin_reliability, per_stat_reliability


def _b(bins):
    return {b["label"]: b for b in bins}


def test_significant_drift_flagged():
    # 40 picks predicted 72% that all LOSE -> obs 0% vs pred 72%, well over 2 SE.
    picks = [{"stat": "PTS", "win_prob": "0.72", "result": "L"} for _ in range(40)]
    hi = _b(bin_reliability(picks))["70%+"]
    assert hi["n"] == 40
    assert hi["obs"] == 0.0 and abs(hi["pred"] - 0.72) < 1e-9
    assert hi["gap"] == pytest.approx(-0.72)
    assert hi["significant"] is True


def test_calibrated_bucket_not_flagged():
    # 100 picks at 60%, exactly 60 wins -> obs == pred, no drift.
    picks = [{"stat": "AST", "win_prob": "0.60", "result": "W" if i < 60 else "L"}
             for i in range(100)]
    b = _b(bin_reliability(picks))["60-65%"]
    assert b["n"] == 100 and abs(b["obs"] - 0.60) < 1e-9
    assert b["significant"] is False


def test_min_n_gates_the_flag():
    # A big miss but only 5 samples -> not flagged when min_n=30, flagged when min_n=5.
    picks = [{"stat": "REB", "win_prob": "0.72", "result": "L"} for _ in range(5)]
    assert _b(bin_reliability(picks, min_n=30))["70%+"]["significant"] is False
    assert _b(bin_reliability(picks, min_n=5))["70%+"]["significant"] is True


def test_excludes_nonprops_pushes_and_unparseable():
    picks = [
        {"stat": "PTS", "win_prob": "0.62", "result": "W"},   # counted
        {"stat": "PTS", "win_prob": "0", "result": "W"},       # parlay/game-line (wp=0)
        {"stat": "PTS", "win_prob": "0.62", "result": "P"},    # push
        {"stat": "PTS", "win_prob": "", "result": "W"},        # no win_prob
        {"stat": "PTS", "win_prob": "abc", "result": "L"},     # unparseable
    ]
    assert sum(b["n"] for b in bin_reliability(picks)) == 1


def test_per_stat_groups_independently():
    picks = [
        {"stat": "PTS", "win_prob": "0.62", "result": "W"},
        {"stat": "ast", "win_prob": "0.62", "result": "L"},   # case-folded
    ]
    res = per_stat_reliability(picks)
    assert set(res) == {"PTS", "AST"}
    assert sum(b["n"] for b in res["PTS"]) == 1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
