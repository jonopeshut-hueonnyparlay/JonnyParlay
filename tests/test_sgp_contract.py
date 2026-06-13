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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
