#!/usr/bin/env python3
"""Tests for the pick_log schema-migration framework (P2.12).

Covers the additions to pick_log_schema.py:
  * register_migration / migrate_row_chain — per-version transform chain
  * migrate_file — file-level runner (no-op when current, dry-run by default,
    atomic rewrite + backup + sidecar on a real migration)

The framework is pure pass-through with no registered migrations (v1→v4 were
all append-only), so the current pick_log (v4) must be a no-op.
"""

from __future__ import annotations

import csv
import sys

import pytest

# engine/ is added to sys.path by the repo-root conftest.py.


# ── migrate_row_chain / register_migration ────────────────────────────────
def test_migrate_row_chain_no_registered_transforms_is_blankfill():
    """With no registered migrations, the chain == migrate_row (blank-fill)."""
    from pick_log_schema import migrate_row, migrate_row_chain
    v1 = {"date": "2026-04-20", "player": "Luka", "stat": "PTS", "result": "W"}
    chained = migrate_row_chain(v1, from_version=1, source_header=list(v1.keys()))
    direct = migrate_row(v1, source_header=list(v1.keys()))
    assert chained == direct


def test_register_migration_applies_transform_in_chain():
    """A registered per-version transform runs for versions < SCHEMA_VERSION."""
    from pick_log_schema import (
        register_migration, migrate_row_chain, _MIGRATIONS, SCHEMA_VERSION,
    )
    saved = dict(_MIGRATIONS)
    try:
        # Tag any row that passes through the v2->v3 step (2 < SCHEMA_VERSION=4).
        register_migration(2, lambda r: {**r, "book": "MIGRATED"})
        out = migrate_row_chain({"date": "2026-04-20", "book": "orig"}, from_version=2)
        assert out["book"] == "MIGRATED"
        # Starting at/after the registered version's successor skips it.
        out2 = migrate_row_chain({"date": "2026-04-20", "book": "orig"}, from_version=3)
        assert out2["book"] == "orig"
    finally:
        _MIGRATIONS.clear()
        _MIGRATIONS.update(saved)


# ── migrate_file ──────────────────────────────────────────────────────────
def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_migrate_file_absent(tmp_path):
    from pick_log_schema import migrate_file
    res = migrate_file(tmp_path / "nope.csv")
    assert res["status"] == "absent"


def test_migrate_file_current_is_noop(tmp_path):
    """A canonical v4 file reports 'current' and is not rewritten."""
    from pick_log_schema import migrate_file, CANONICAL_HEADER
    p = tmp_path / "log.csv"
    _write_csv(p, CANONICAL_HEADER, [[""] * len(CANONICAL_HEADER)])
    before = p.read_bytes()
    res = migrate_file(p, dry_run=False)
    assert res["status"] == "current"
    assert p.read_bytes() == before  # untouched


def test_migrate_file_dry_run_reports_without_writing(tmp_path):
    """A v1 file dry-runs to 'would_migrate' and is left untouched."""
    from pick_log_schema import migrate_file
    v1_header = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat",
        "line", "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
    ]
    p = tmp_path / "log.csv"
    _write_csv(p, v1_header, [["2026-04-20"] + [""] * (len(v1_header) - 1)])
    before = p.read_bytes()
    res = migrate_file(p)  # dry_run defaults True
    assert res["status"] == "would_migrate"
    assert res["from_version"] == 1
    assert res["to_version"] == 5
    assert "over_p_raw" in res["added_columns"]
    assert "clv_corrected" in res["added_columns"]
    assert p.read_bytes() == before  # not written


def test_migrate_file_rewrites_and_backs_up(tmp_path):
    """A real migration rewrites to canonical, backs up, and writes a sidecar."""
    from pick_log_schema import (
        migrate_file, CANONICAL_HEADER, read_schema_sidecar, SCHEMA_VERSION,
    )
    v1_header = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat",
        "line", "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
    ]
    p = tmp_path / "log.csv"
    _write_csv(p, v1_header, [["2026-04-20"] + [""] * (len(v1_header) - 1)])

    res = migrate_file(p, dry_run=False)
    assert res["status"] == "migrated"

    # File now has the canonical header.
    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert list(reader.fieldnames) == CANONICAL_HEADER
        out_rows = list(reader)
    assert len(out_rows) == 1
    assert out_rows[0]["date"] == "2026-04-20"
    assert out_rows[0]["over_p_raw"] == ""  # filled blank

    # Backup of the original was created.
    assert (tmp_path / "log.v1.bak.csv").exists()

    # Sidecar reflects the current version.
    sidecar = read_schema_sidecar(p)
    assert sidecar is not None
    assert sidecar["schema_version"] == SCHEMA_VERSION


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
