"""Tests for engine/crps.py (#11) + the source_shadow CRPS wiring."""
import math

import crps
from name_utils import name_key


# ── crps_normal ─────────────────────────────────────────────────────────────

def test_crps_normal_known_value():
    # CRPS(N(0,1), 0) = 2*phi(0) - 1/sqrt(pi) = sqrt(2/pi) - 1/sqrt(pi).
    expected = math.sqrt(2.0 / math.pi) - 1.0 / math.sqrt(math.pi)
    assert math.isclose(crps.crps_normal(0.0, 1.0, 0.0), expected, abs_tol=1e-12)


def test_crps_normal_point_forecast_is_abs_error():
    assert crps.crps_normal(10.0, 0.0, 7.0) == 3.0   # sigma<=0 -> |y-mu|


def test_crps_normal_increases_with_error():
    near = crps.crps_normal(20.0, 5.0, 21.0)
    far = crps.crps_normal(20.0, 5.0, 35.0)
    assert far > near


def test_crps_normal_sharper_better_when_accurate():
    # When the mean is exactly right, a sharper (smaller sigma) forecast scores lower.
    sharp = crps.crps_normal(20.0, 2.0, 20.0)
    wide = crps.crps_normal(20.0, 8.0, 20.0)
    assert sharp < wide


# ── crps_ensemble ───────────────────────────────────────────────────────────

def test_crps_ensemble_point_mass_is_zero():
    assert crps.crps_ensemble([5.0, 5.0, 5.0], 5.0) == 0.0


def test_crps_ensemble_known_small_case():
    # samples [0,2], y=1: term1 = (1+1)/2 = 1; term2 = (0+2+2+0)/4 = 1; CRPS = 0.5.
    assert math.isclose(crps.crps_ensemble([0.0, 2.0], 1.0), 0.5, abs_tol=1e-12)


def test_crps_ensemble_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        crps.crps_ensemble([], 1.0)


# ── crps_from_cdf ───────────────────────────────────────────────────────────

def test_crps_from_cdf_step_at_y_is_zero():
    cdf = lambda k: 1.0 if k >= 2 else 0.0   # point mass at 2
    assert crps.crps_from_cdf(cdf, 2.0, 0, 5) == 0.0


def test_crps_from_cdf_matches_manual_sum():
    cdf = lambda k: {0: 0.2, 1: 0.6, 2: 1.0}[k]
    y = 1
    # sum (F(k)-1{y<=k})^2 over k=0,1,2: (0.2-0)^2 + (0.6-1)^2 + (1.0-1)^2 = 0.04+0.16+0 = 0.20
    assert math.isclose(crps.crps_from_cdf(cdf, y, 0, 2), 0.20, abs_tol=1e-12)


# ── source_shadow CRPS wiring ───────────────────────────────────────────────

def test_shadow_emits_crps_when_actuals_supplied():
    import source_shadow as ss
    nk = name_key("Anthony Edwards")
    pick = {"date": "2026-06-26", "sport": "NBA", "player": "Anthony Edwards",
            "stat": "PTS", "line": "27.5", "direction": "over", "proj": "26.0", "result": "L"}
    # EdgeModel projects 30; the actual was 31 -> EdgeModel's mean is closer -> lower CRPS.
    em = {(nk, "PTS"): 30.0}
    actuals = {("2026-06-26", nk, "PTS"): 31.0}
    row = ss.compare_rows([pick], adapter_fetch=lambda *a, **k: em, actuals=actuals)[0]
    assert row["actual_value"] == 31.0
    assert isinstance(row["live_crps"], float) and isinstance(row["em_crps"], float)
    assert row["em_crps"] < row["live_crps"]   # EM mean nearer the realized value


def test_shadow_crps_blank_without_actuals():
    import source_shadow as ss
    nk = name_key("Anthony Edwards")
    pick = {"date": "2026-06-26", "sport": "NBA", "player": "Anthony Edwards",
            "stat": "PTS", "line": "27.5", "direction": "over", "proj": "26.0", "result": "L"}
    row = ss.compare_rows([pick], adapter_fetch=lambda *a, **k: {(nk, "PTS"): 30.0})[0]
    assert row["actual_value"] == "" and row["live_crps"] == "" and row["em_crps"] == ""
