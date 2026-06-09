#!/usr/bin/env python3
"""Regression tests for Section 20 — shadow/manual leakage + write-time normalization.

Covers:
  H-6              results_graphic drops manual + shadow rows before rendering
  H-14 / PICK-H-1  post_nrfi_bonus routes shadow sports → pick_log_mlb.csv + no webhook
  PICK-H-3         normalize_american_odds always emits sign-prefixed American odds
  PICK-H-4         assert_manual_row_valid rejects rows missing required fields
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# PICK_LOG_AUDIT H-3 — normalize_american_odds
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("inp,expected", [
    (105, "+105"),
    (-110, "-110"),
    ("+108", "+108"),
    ("-115", "-115"),
    ("105", "+105"),          # THE bug — bare positive was broken for analyze_picks
    ("  +105  ", "+105"),     # whitespace tolerated
    (0, "0"),                 # zero has no sign
    ("", ""),                 # empty preserved
    (None, ""),               # None preserved
    ("abc", ""),              # unparseable → blank (defensive)
    (250.0, "+250"),          # float tolerated
    (-7.0, "-7"),
])
def test_normalize_american_odds(inp, expected):
    from pick_log_schema import normalize_american_odds
    assert normalize_american_odds(inp) == expected


# ─────────────────────────────────────────────────────────────────
# PICK_LOG_AUDIT H-4 — manual row validator
# ─────────────────────────────────────────────────────────────────

def _valid_manual_row():
    return {
        "date": "2026-04-20",
        "sport": "NBA",
        "stat": "PTS",
        "line": "24.5",
        "direction": "over",
        "odds": "+115",
        "book": "draftkings",
        "size": "1.25",
    }


def test_manual_row_valid_passes():
    from pick_log_schema import assert_manual_row_valid
    assert_manual_row_valid(_valid_manual_row())  # does not raise


def test_manual_row_missing_book_rejected():
    from pick_log_schema import (
        assert_manual_row_valid,
        ManualRowValidationError,
    )
    row = _valid_manual_row()
    row["book"] = ""
    with pytest.raises(ManualRowValidationError, match="book"):
        assert_manual_row_valid(row)


def test_manual_row_missing_odds_rejected():
    from pick_log_schema import (
        assert_manual_row_valid,
        ManualRowValidationError,
    )
    row = _valid_manual_row()
    row["odds"] = ""
    with pytest.raises(ManualRowValidationError, match="odds"):
        assert_manual_row_valid(row)


def test_manual_row_missing_multiple_fields_lists_all():
    from pick_log_schema import validate_manual_row
    row = _valid_manual_row()
    row["book"] = ""
    row["size"] = ""
    row["odds"] = None
    missing = validate_manual_row(row)
    assert set(missing) >= {"book", "size", "odds"}


def test_manual_row_whitespace_only_counts_as_missing():
    from pick_log_schema import validate_manual_row
    row = _valid_manual_row()
    row["book"] = "   "
    assert "book" in validate_manual_row(row)


# ─────────────────────────────────────────────────────────────────
# PICK_LOG H-1 / AUDIT H-14 — post_nrfi_bonus shadow routing
# ─────────────────────────────────────────────────────────────────

def test_post_nrfi_bonus_routes_mlb_to_shadow_log(tmp_path, monkeypatch):
    """MLB went live 2026-05-20: MLB bonuses now go to pick_log.csv (main log)
    and post to Discord. (WNBA also live as of 2026-06-09 — no shadow sports remain.)
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    import secrets_config as sc
    monkeypatch.setattr(sc, "DISCORD_BONUS_WEBHOOK", "https://fake/webhook",
                        raising=False)

    # MLB is live — Discord posting is expected; stub requests.post to succeed silently.
    import requests as _requests_mod
    monkeypatch.setattr(_requests_mod, "post", lambda *a, **kw: None)

    spec_path = Path(__file__).resolve().parent.parent / "post_nrfi_bonus.py"
    src = spec_path.read_text(encoding="utf-8")
    shimmed = src.replace(
        'DATA_DIR = Path(__file__).parent / "data"',
        f'DATA_DIR = Path(r"{data_dir}")',
    )
    # Standard guard means exec() won't auto-call main(); invoke it explicitly.
    ns: dict = {"__name__": "post_nrfi_bonus_test_shim", "__file__": str(spec_path)}
    exec(compile(shimmed, str(spec_path), "exec"), ns)
    ns["main"]([])

    main_log = data_dir / "pick_log.csv"
    shadow_log = data_dir / "pick_log_mlb.csv"

    # MLB is live — row goes to MAIN log, NOT the old shadow log.
    assert main_log.exists(), (
        "Main pick_log.csv was not written — MLB is live and should route to the main log."
    )
    assert not shadow_log.exists(), (
        "pick_log_mlb.csv was written — MLB should no longer route to the shadow log."
    )

    # Verify the row is canonical-shaped and odds are sign-prefixed (now in main log).
    with open(main_log, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    row = rows[0]
    assert row["sport"] == "MLB"
    assert row["run_type"] == "bonus"
    assert row["odds"] == "+108", (
        f"Odds must be sign-prefixed at write time (H-3). Got: {row['odds']!r}"
    )


def test_post_nrfi_bonus_log_path_helper_routes_by_sport():
    """Smoke-test the routing helper in isolation — no filesystem writes."""
    import importlib
    # Fresh import so module-level DATA_DIR doesn't conflict with the test above.
    for modname in ("post_nrfi_bonus",):
        if modname in sys.modules:
            del sys.modules[modname]
    # Add repo root so `import post_nrfi_bonus` works.
    repo_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(repo_root))
    try:
        import post_nrfi_bonus as pnb
    except Exception as e:
        pytest.skip(f"Cannot import post_nrfi_bonus (likely side effects): {e}")

    # NBA → main log
    assert pnb._log_path_for("NBA") == pnb.MAIN_LOG
    # MLB is live (2026-05-20) → main log
    assert pnb._log_path_for("MLB") == pnb.MAIN_LOG
    assert pnb._log_path_for("mlb") == pnb.MAIN_LOG
    # WNBA live (2026-06-09) → main log
    assert pnb._log_path_for("WNBA") == pnb.MAIN_LOG
    assert pnb.SHADOW_LOGS == {}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
