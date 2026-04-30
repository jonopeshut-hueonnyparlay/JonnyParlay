#!/usr/bin/env python3
"""Regression tests for audit H-3 — pick_log schema contract + migration.

Before consolidation, run_picks.py had two separate HEADER definitions
(one local to log_picks(), one local to _log_bonus_pick()) that drifted
whenever a new column was added. There was also no migration for readers
encountering old-schema logs — DictReader would silently return rows
missing the expected keys.

These tests lock in:
  - CANONICAL_HEADER is the single source of truth
  - run_picks + pick_log_io both reference the canonical object
  - migrate_row() upgrades v1 rows to canonical shape with blanks
  - validate_header() reports missing + unknown columns
  - read_rows_locked_if_exists defaults to migrate=True
  - migrate=False opts out of migration for the raw read
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# Canonical invariants
# ─────────────────────────────────────────────────────────────────

def test_canonical_header_is_28_cols():
    from pick_log_schema import CANONICAL_HEADER
    assert len(CANONICAL_HEADER) == 28, (
        f"CANONICAL_HEADER length locked at 28 (v3); got {len(CANONICAL_HEADER)}. "
        "If adding a new column: bump SCHEMA_VERSION, update this test, and "
        "verify migrate_row() still produces canonical rows."
    )


def test_canonical_header_has_no_duplicates():
    from pick_log_schema import CANONICAL_HEADER
    assert len(set(CANONICAL_HEADER)) == len(CANONICAL_HEADER)


def test_canonical_header_contains_every_v2_only_column():
    """CLV + context columns must be in the canonical schema."""
    from pick_log_schema import CANONICAL_HEADER
    for col in ("closing_odds", "clv", "card_slot", "is_home",
                "context_verdict", "context_reason", "context_score"):
        assert col in CANONICAL_HEADER, f"v2 column '{col}' missing from canonical"


def test_schema_version_is_3():
    from pick_log_schema import SCHEMA_VERSION
    assert SCHEMA_VERSION == 3


# ─────────────────────────────────────────────────────────────────
# No-drift identity: run_picks + pick_log_io use the same object
# ─────────────────────────────────────────────────────────────────

def test_run_picks_uses_canonical_header_object():
    """run_picks must NOT re-declare HEADER locally — identity check."""
    import pick_log_schema
    import run_picks
    assert run_picks.CANONICAL_HEADER is pick_log_schema.CANONICAL_HEADER


def test_run_picks_exports_schema_version_alias():
    import pick_log_schema
    import run_picks
    assert run_picks.PICK_LOG_SCHEMA_VERSION == pick_log_schema.SCHEMA_VERSION


def test_pick_log_io_uses_canonical_helpers():
    import pick_log_schema
    import pick_log_io
    assert pick_log_io.migrate_row is pick_log_schema.migrate_row
    assert pick_log_io.CANONICAL_HEADER is pick_log_schema.CANONICAL_HEADER


# ─────────────────────────────────────────────────────────────────
# migrate_row — covers the real drift scenarios
# ─────────────────────────────────────────────────────────────────

def test_migrate_row_fills_missing_v2_columns_for_v1_row():
    """A row from a pre-CLV log should come back with blank CLV + context cols."""
    from pick_log_schema import migrate_row, CANONICAL_HEADER
    v1_row = {
        "date": "2026-01-01", "run_time": "09:00", "run_type": "primary",
        "sport": "NBA", "player": "LeBron James", "team": "LAL",
        "stat": "PTS", "line": "28.5", "direction": "over",
        "proj": "30.1", "win_prob": "0.58", "edge": "0.05", "odds": "-110",
        "book": "draftkings", "tier": "T1", "pick_score": "72.0",
        "size": "1.50", "game": "LAL@BOS", "mode": "", "result": "win",
    }
    out = migrate_row(v1_row, source_header=list(v1_row.keys()))
    # Every canonical column present.
    assert set(out.keys()) == set(CANONICAL_HEADER)
    # v1 values preserved.
    assert out["player"] == "LeBron James"
    assert out["result"] == "win"
    # v2-only columns defaulted to blank.
    assert out["closing_odds"] == ""
    assert out["clv"] == ""
    assert out["context_verdict"] == ""
    assert out["context_score"] == ""


def test_migrate_row_drops_unknown_columns():
    from pick_log_schema import migrate_row, CANONICAL_HEADER
    weird_row = {"date": "2026-04-20", "something_new": "alien", "player": "X"}
    out = migrate_row(weird_row)
    assert "something_new" not in out
    assert out["player"] == "X"
    assert set(out.keys()) == set(CANONICAL_HEADER)


def test_migrate_row_stringifies_non_string_values():
    """csv.DictReader always yields strings, but defend against programmatic callers."""
    from pick_log_schema import migrate_row
    out = migrate_row({"date": "2026-04-20", "line": 28.5, "win_prob": 0.58})
    assert out["line"] == "28.5"
    assert out["win_prob"] == "0.58"


def test_migrate_row_handles_none_values():
    from pick_log_schema import migrate_row
    out = migrate_row({"date": None, "player": None})
    assert out["date"] == ""
    assert out["player"] == ""


def test_migrate_row_on_empty_input():
    from pick_log_schema import migrate_row, CANONICAL_HEADER
    out = migrate_row({})
    assert set(out.keys()) == set(CANONICAL_HEADER)
    assert all(v == "" for v in out.values())


# ─────────────────────────────────────────────────────────────────
# validate_header / detect_schema_version
# ─────────────────────────────────────────────────────────────────

def test_validate_header_on_v1_log_flags_missing_v2_columns():
    from pick_log_schema import validate_header
    v1_header = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
        "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
    ]
    missing, unknown = validate_header(v1_header)
    assert "closing_odds" in missing
    assert "context_verdict" in missing
    assert unknown == []


def test_validate_header_on_canonical_log_reports_clean():
    from pick_log_schema import validate_header, CANONICAL_HEADER
    missing, unknown = validate_header(list(CANONICAL_HEADER))
    assert missing == []
    assert unknown == []


def test_validate_header_flags_unknown_columns():
    from pick_log_schema import validate_header, CANONICAL_HEADER
    header_plus_alien = list(CANONICAL_HEADER) + ["alien_col"]
    missing, unknown = validate_header(header_plus_alien)
    assert missing == []
    assert unknown == ["alien_col"]


def test_detect_schema_version_v1():
    from pick_log_schema import detect_schema_version
    assert detect_schema_version(
        ["date", "run_time", "player", "stat", "line", "result"]
    ) == 1


def test_detect_schema_version_v2():
    from pick_log_schema import detect_schema_version
    assert detect_schema_version(
        ["date", "player", "closing_odds"]
    ) == 2


def test_detect_schema_version_empty_returns_zero():
    from pick_log_schema import detect_schema_version
    assert detect_schema_version([]) == 0
    assert detect_schema_version(None) == 0


# ─────────────────────────────────────────────────────────────────
# Reader integration: pick_log_io migrates by default
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def v1_pick_log(tmp_path):
    """Write a pre-CLV (20-col) pick_log and return its path + lock."""
    p = tmp_path / "pick_log.csv"
    v1_header = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
        "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
    ]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=v1_header)
        w.writeheader()
        w.writerow({
            "date": "2026-01-15", "run_time": "09:00", "run_type": "primary",
            "sport": "NBA", "player": "Nikola Jokic", "team": "DEN",
            "stat": "AST", "line": "9.5", "direction": "over",
            "proj": "10.8", "win_prob": "0.59", "edge": "0.06",
            "odds": "-120", "book": "fanduel", "tier": "T1",
            "pick_score": "78.5", "size": "2.00", "game": "DEN@LAL",
            "mode": "", "result": "win",
        })
    return p


def test_reader_migrates_v1_row_by_default(v1_pick_log):
    from pick_log_io import read_rows_locked_if_exists
    from pick_log_schema import CANONICAL_HEADER
    rows, fieldnames = read_rows_locked_if_exists(v1_pick_log)
    assert len(rows) == 1
    # Rows are canonical-shaped even though the file on disk is v1.
    assert set(rows[0].keys()) == set(CANONICAL_HEADER)
    assert rows[0]["player"] == "Nikola Jokic"
    assert rows[0]["closing_odds"] == ""       # filled by migration
    assert rows[0]["context_verdict"] == ""    # filled by migration
    # fieldnames still reflects WHAT'S ON DISK, not the migrated shape —
    # callers that do read-modify-write rely on that to preserve the original
    # header structure.
    assert "closing_odds" not in fieldnames
    assert "context_verdict" not in fieldnames


def test_reader_migrate_false_returns_raw_rows(v1_pick_log):
    """Opt-out escape hatch for callers that need the raw on-disk shape."""
    from pick_log_io import read_rows_locked_if_exists
    rows, _ = read_rows_locked_if_exists(v1_pick_log, migrate=False)
    assert len(rows) == 1
    # Raw row has ONLY the 20 v1 columns.
    assert "closing_odds" not in rows[0]
    assert "context_verdict" not in rows[0]
    assert rows[0]["player"] == "Nikola Jokic"


def test_reader_returns_empty_for_missing_file(tmp_path):
    from pick_log_io import read_rows_locked_if_exists
    rows, fieldnames = read_rows_locked_if_exists(tmp_path / "nope.csv")
    assert rows == []
    assert fieldnames == []


def test_reader_tolerates_unknown_columns(tmp_path):
    """A log with an unknown column shouldn't crash — the column is just dropped."""
    from pick_log_io import read_rows_locked_if_exists
    from pick_log_schema import CANONICAL_HEADER
    p = tmp_path / "pick_log.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        header = list(CANONICAL_HEADER) + ["future_column"]
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerow({**{c: "" for c in CANONICAL_HEADER},
                    "date": "2026-04-20", "player": "Z", "future_column": "alien"})
    rows, fieldnames = read_rows_locked_if_exists(p)
    assert len(rows) == 1
    assert "future_column" not in rows[0]     # dropped on migrate
    assert "future_column" in fieldnames      # still reported on disk


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
