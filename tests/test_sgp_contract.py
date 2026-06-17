"""SGP re-export contract: symbols sgp_builder.py / mlb_sgp_builder.py import
from run_picks must remain importable after the Phase 1/2 module split.

Both builders do `from run_picks import ...` for these six symbols at call time.
If the refactor ever drops a re-export, the builders break at runtime — this
test fails fast instead. (Not covered by tests/test_section24_data_contract.py.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest


def test_sgp_contract_symbols_importable():
    from run_picks import (  # noqa: F401
        PICK_LOG_PATH,
        _pick_log_lock,
        _normalize_odds,
        _normalize_size,
        _write_schema_sidecar,
        _webhook_post,
    )


@pytest.mark.parametrize("name", [
    "PICK_LOG_PATH",
    "_pick_log_lock",
    "_normalize_odds",
    "_normalize_size",
    "_write_schema_sidecar",
    "_webhook_post",
])
def test_run_picks_exposes_symbol(name):
    import run_picks
    assert hasattr(run_picks, name), f"run_picks must re-export {name} for the SGP builders"


def test_callables_are_callable():
    import run_picks
    for name in ("_pick_log_lock", "_normalize_odds", "_normalize_size",
                 "_write_schema_sidecar", "_webhook_post"):
        assert callable(getattr(run_picks, name)), f"{name} should be callable"


# ── NB_R single-source contract ──────────────────────────────────────────────
# Shared NBA dispersion (3PM/AST/REB) lives ONLY in calibrated.NB_R; sgp_builder
# derives those entries from it. These guard against the hand-mirrored drift that
# P1.3 had to re-pin. BLK/STL are SGP-only and legitimately absent from calibrated.

def test_sgp_nb_r_shared_stats_single_sourced():
    import calibrated
    import sgp_builder
    shared = {"3PM", "AST", "REB"}
    for stat in shared:
        assert stat in calibrated.NB_R, f"{stat} must live in calibrated.NB_R"
        assert sgp_builder.NB_R[stat] == calibrated.NB_R[stat], (
            f"sgp_builder.NB_R[{stat}]={sgp_builder.NB_R[stat]} drifted from "
            f"calibrated.NB_R[{stat}]={calibrated.NB_R[stat]} — must be single-sourced"
        )


def test_sgp_nb_r_only_blk_stl_are_local():
    import calibrated
    import sgp_builder
    # SGP-only stats must NOT shadow a calibrated entry (would re-introduce drift).
    assert set(sgp_builder._SGP_ONLY_NB_R) == {"BLK", "STL"}
    assert not (set(sgp_builder._SGP_ONLY_NB_R) & set(calibrated.NB_R)), (
        "SGP-only NB_R stats must not also exist in calibrated.NB_R"
    )


def test_sgp_nb_r_covers_nb_stats():
    import sgp_builder
    # Every NB_STATS entry resolves to a value (the load-time invariant guarantees
    # this, but assert it explicitly so a regression is a test failure, not a 500).
    for stat in sgp_builder.NB_STATS:
        assert stat in sgp_builder.NB_R, f"NB_STATS {stat} missing from derived NB_R"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
