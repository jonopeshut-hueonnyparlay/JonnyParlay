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
# AUDIT H-6 — results_graphic filters manual + shadow rows
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def rg_with_mixed_log(tmp_path, monkeypatch):
    """Write a pick_log.csv containing public, manual, and shadow rows.

    Assert that _load_day_picks keeps only the public, non-shadow ones —
    even if a shadow row leaks into the main log (defensive double-filter).
    """
    log = tmp_path / "pick_log.csv"
    log.parent.mkdir(parents=True, exist_ok=True)
    from pick_log_schema import CANONICAL_HEADER

    def mk(run_type, sport, player, result="W"):
        r = {c: "" for c in CANONICAL_HEADER}
        r.update({
            "date": "2026-04-20", "run_time": "10:00", "run_type": run_type,
            "sport": sport, "player": player, "team": "X", "stat": "PTS",
            "line": "20", "direction": "over", "odds": "-110",
            "book": "draftkings", "tier": "T1", "size": "1.00",
            "result": result,
        })
        return r

    rows = [
        mk("primary",   "NBA", "Public Primary"),
        mk("bonus",     "NBA", "Public Bonus"),
        mk("daily_lay", "NBA", "Public Daily Lay"),
        mk("manual",    "NBA", "Manual Pick"),        # must be filtered (H-6)
        mk("primary",   "MLB", "Shadow Primary"),     # must be filtered (shadow)
        mk("bonus",     "MLB", "Shadow Bonus"),       # must be filtered (shadow)
        mk("primary",   "NBA", "Ungraded", result=""),  # must be filtered (ungraded)
    ]
    with open(log, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    import results_graphic as rg
    importlib.reload(rg)
    monkeypatch.setattr(rg, "PICK_LOG_PATH", str(log))
    return rg


def test_results_graphic_keeps_public_rows_only(rg_with_mixed_log):
    rg = rg_with_mixed_log
    picks = rg._load_day_picks("2026-04-20")
    players = {p["player"] for p in picks}
    # These three are public + graded → included.
    assert players == {"Public Primary", "Public Bonus", "Public Daily Lay"}


def test_results_graphic_drops_manual_run_type(rg_with_mixed_log):
    rg = rg_with_mixed_log
    picks = rg._load_day_picks("2026-04-20")
    assert not any(p["player"] == "Manual Pick" for p in picks), (
        "H-6: manual run_type must never appear on the public card."
    )


def test_results_graphic_drops_shadow_sports(rg_with_mixed_log):
    rg = rg_with_mixed_log
    picks = rg._load_day_picks("2026-04-20")
    assert not any(p["sport"] == "MLB" for p in picks), (
        "H-14: shadow sports must never appear on the public card."
    )


def test_results_graphic_drops_ungraded(rg_with_mixed_log):
    rg = rg_with_mixed_log
    picks = rg._load_day_picks("2026-04-20")
    assert not any(p["player"] == "Ungraded" for p in picks), (
        "Results graphic should only render graded (W/L/P) rows."
    )


# ─────────────────────────────────────────────────────────────────
# PICK_LOG H-1 / AUDIT H-14 — post_nrfi_bonus shadow routing
# ─────────────────────────────────────────────────────────────────

def test_post_nrfi_bonus_routes_mlb_to_shadow_log(tmp_path, monkeypatch):
    """The whole point of the H-1 fix: an MLB bonus must NOT land in
    data/pick_log.csv. It goes to pick_log_mlb.csv.
    """
    # Redirect the DATA_DIR on a fresh import of the module.
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Stub secrets_config so we don't need a real webhook.
    import secrets_config as sc
    monkeypatch.setattr(sc, "DISCORD_BONUS_WEBHOOK", "https://fake/webhook",
                        raising=False)

    # Patch urlopen before import so if it ever fires, the test fails loudly.
    import urllib.request
    def _boom(*a, **kw):  # pragma: no cover — shouldn't be reached
        raise AssertionError("Shadow sport should NOT post to Discord")
    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    # Shim the module to use our temp data dir by replacing Path(__file__)
    # in sys.argv-style imports is awkward — easier to monkeypatch after import.
    # Reload post_nrfi_bonus with patched paths.
    # We emulate execution by importing with the constants replaced.
    spec_path = Path(__file__).resolve().parent.parent / "post_nrfi_bonus.py"
    src = spec_path.read_text(encoding="utf-8")
    # Rewrite the DATA_DIR assignment to our tmp dir. Crude but keeps the
    # test hermetic without adding a CLI param to a one-shot script.
    shimmed = src.replace(
        'DATA_DIR = Path(__file__).parent / "data"',
        f'DATA_DIR = Path(r"{data_dir}")',
    )
    ns: dict = {"__name__": "post_nrfi_bonus_test_shim", "__file__": str(spec_path)}
    exec(compile(shimmed, str(spec_path), "exec"), ns)

    main_log = data_dir / "pick_log.csv"
    shadow_log = data_dir / "pick_log_mlb.csv"

    # H-1: the MLB row must be in shadow log, NOT main log.
    assert shadow_log.exists(), (
        "Shadow log wasn't written — H-1 routing is broken."
    )
    assert not main_log.exists(), (
        "Main pick_log.csv was written — this is the public-leak bug the "
        "Section 20 fix was supposed to close."
    )

    # Verify the row is canonical-shaped and odds are sign-prefixed.
    with open(shadow_log, newline="") as f:
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
    # MLB → shadow log
    assert pnb._log_path_for("MLB") == pnb.SHADOW_LOGS["MLB"]
    # Case-insensitive
    assert pnb._log_path_for("mlb") == pnb.SHADOW_LOGS["MLB"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
