"""Sanity tests for fitted constants in calibrated.py.

Existence / type / range / locked-value checks only. Tier-routing structure
(STAT_FAMILY_TIER, TIERS floors, BM_SHRINKAGE_WEIGHT covers-all-tiers /
0<w<=1) is already covered by tests/test_plan9_tier_restructure.py and is NOT
duplicated here. F5_SCALAR and BLEND_ALPHA live in thresholds.py, not
calibrated.py — they are tested in tests/test_thresholds.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

import calibrated
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
    # Task#1 2026-06-16: ER re-aligned to the starts-only fit (was 2.62,
    # relief-contaminated). HA synced 2026-07-02 to EdgeModel's starts-only
    # NB_R_HA=50.0 (near-Poisson; was held at the relief-contaminated 13.41;
    # market remains G_HA_SUSPENDED).
    assert NB_R["ER"] == pytest.approx(4.75)
    assert NB_R["HA"] == pytest.approx(50.0)


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


# ---------------------------------------------------------------------------
# R1: _load_team_sigmas() must never crash calibrated.py's import on a
# malformed per-sport artifact. Reuses the module-__file__-monkeypatch
# pattern already established in tests/test_check_pricing_core_lock.py.
# ---------------------------------------------------------------------------

_VALID_SPORT_DATA = {
    "NYY": {"score_sigma": 4.2, "n_games": 45},
    "BOS": {"score_sigma": 4.5, "n_games": 50},
}


def _write_data_dir(tmp_path, files: dict):
    """files: {filename: raw text to write}. Fakes calibrated.py's own
    __file__ so `Path(__file__).parent.parent / "data"` resolves under
    tmp_path instead of the real repo."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for fname, text in files.items():
        (data_dir / fname).write_text(text, encoding="utf-8")
    return tmp_path / "engine" / "calibrated.py"


def test_valid_artifacts_still_load_exactly_as_before(tmp_path, monkeypatch):
    fake_file = _write_data_dir(tmp_path, {
        "team_sigmas_mlb.json": json.dumps(_VALID_SPORT_DATA),
    })
    monkeypatch.setattr(calibrated, "__file__", str(fake_file))
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS", {})
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS_MEANSQ", {})

    calibrated._load_team_sigmas()

    assert calibrated._TEAM_SIGMAS["MLB"] == _VALID_SPORT_DATA
    assert calibrated._TEAM_SIGMAS_MEANSQ["MLB"] == pytest.approx(
        (4.2 ** 2 + 4.5 ** 2) / 2)


def test_malformed_json_does_not_crash_load(tmp_path, monkeypatch):
    fake_file = _write_data_dir(tmp_path, {
        "team_sigmas_mlb.json": "{not valid json",
    })
    monkeypatch.setattr(calibrated, "__file__", str(fake_file))
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS", {})
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS_MEANSQ", {})

    calibrated._load_team_sigmas()  # must not raise


def test_malformed_sport_logs_error(tmp_path, monkeypatch):
    fake_file = _write_data_dir(tmp_path, {
        "team_sigmas_mlb.json": "{not valid json",
    })
    monkeypatch.setattr(calibrated, "__file__", str(fake_file))
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS", {})
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS_MEANSQ", {})

    logged = []
    monkeypatch.setattr(calibrated.log, "error",
                         lambda *a, **k: logged.append((a, k)))

    calibrated._load_team_sigmas()

    assert logged, "a malformed artifact must log, never silently continue"
    assert any("MLB" in str(a) for a, _k in logged)


def test_other_valid_sports_still_load_when_one_is_malformed(tmp_path, monkeypatch):
    fake_file = _write_data_dir(tmp_path, {
        "team_sigmas_mlb.json": "{not valid json",
        "team_sigmas_nhl.json": json.dumps(_VALID_SPORT_DATA),
    })
    monkeypatch.setattr(calibrated, "__file__", str(fake_file))
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS", {})
    monkeypatch.setattr(calibrated, "_TEAM_SIGMAS_MEANSQ", {})

    calibrated._load_team_sigmas()

    assert "MLB" not in calibrated._TEAM_SIGMAS, (
        "a malformed sport must not appear in _TEAM_SIGMAS at all -- "
        "get_game_sigma()'s existing .get(sport, {}) fallback depends on "
        "the key being absent, not present-but-empty")
    assert calibrated._TEAM_SIGMAS["NHL"] == _VALID_SPORT_DATA


def test_downstream_importers_remain_functional():
    """Smoke check: calibrated.py's real importers must still import cleanly.
    Guards against a future regression reintroducing an import-time crash."""
    import prob_core  # noqa: F401
    import health_check  # noqa: F401
    import team_resolve  # noqa: F401


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
