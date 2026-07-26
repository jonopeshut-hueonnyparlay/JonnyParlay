"""Phase 3 P0 — pick_log schema bypass fixes (RISK_REGISTER.md R2, R3).

Two confirmed-live bugs, tracked in docs/PHASE_3_EXECUTION_PLAN.md T1/T2,
governed by the already-accepted docs/ADR/ADR-005-cross-repo-interface-
versioning.md (no new architectural decision made here):

  T1 (R2) — grade_picks.py's own _read_rows_locked() never called
            migrate_row(), so a legacy-schema log (e.g. pick_log_manual.csv,
            stuck at schema v3 while the main log is at v6) was graded with
            raw, unmigrated rows and written back under its own stale
            on-disk header forever.

  T2 (R3) — run_picks.py's --log-manual writer used a hardcoded 29-value
            positional csv.writer row against a 33-column CANONICAL_HEADER,
            silently dropping source/model_version/run_id/clv_corrected for
            every manually-logged pick.

Run:
    python -m pytest tests/test_phase3_p0_pick_log_schema_fixes.py -v
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from pick_log_schema import CANONICAL_HEADER, SCHEMA_VERSION  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

_V3_HEADER = [  # 28 columns: v1(20) + v2(7: closing_odds..context_score) + v3(legs)
    "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
    "direction", "proj", "win_prob", "edge", "odds", "book",
    "tier", "pick_score", "size", "game", "mode", "result",
    "closing_odds", "clv", "card_slot", "is_home",
    "context_verdict", "context_reason", "context_score", "legs",
]


def _write_v3_log(path: Path, rows: list[dict]) -> None:
    """Write a CSV under the legacy v3 (28-col) header -- matches the real,
    confirmed-live shape of data/pick_log_manual.csv before this fix."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_V3_HEADER, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _V3_HEADER})


def _write_canonical_log(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(CANONICAL_HEADER), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CANONICAL_HEADER})


# ─────────────────────────────────────────────────────────────────
# T1 (R2) — grade_picks._read_rows_locked migration + header upgrade
# ─────────────────────────────────────────────────────────────────

def test_read_rows_locked_migrates_v3_rows_to_canonical_shape(tmp_path):
    """A v3 (28-col) log must read back with every CANONICAL_HEADER key
    present, not just the 28 that were on disk -- this is the exact gap
    that left pick_log_manual.csv's source/model_version/run_id/
    clv_corrected always missing when graded."""
    from grade_picks import _read_rows_locked

    log = tmp_path / "pick_log_manual.csv"
    _write_v3_log(log, [{
        "date": "2026-04-19", "player": "Test A", "stat": "AST", "line": "6.5",
        "direction": "over", "odds": "-110", "book": "fanduel", "size": "1.00",
        "result": "W",
    }])

    rows, fieldnames = _read_rows_locked(log)

    assert len(rows) == 1
    for col in CANONICAL_HEADER:
        assert col in rows[0], f"migrated row missing canonical column {col!r}"
    # Columns that never existed in v3 must be present-but-blank, not absent.
    for col in ("source", "model_version", "run_id", "clv_corrected"):
        assert rows[0][col] == ""
    # Pre-existing data must survive the migration untouched.
    assert rows[0]["result"] == "W"
    assert rows[0]["player"] == "Test A"


def test_read_rows_locked_returns_canonical_header_not_on_disk_header(tmp_path):
    """The second return value must be CANONICAL_HEADER so a caller that
    writes back with it (grade_picks._atomic_write_rows) upgrades the
    file's on-disk header instead of perpetuating the legacy shape
    forever."""
    from grade_picks import _read_rows_locked

    log = tmp_path / "pick_log_manual.csv"
    _write_v3_log(log, [{"date": "2026-04-19", "result": "W"}])

    _, fieldnames = _read_rows_locked(log)

    assert list(fieldnames) == list(CANONICAL_HEADER)


def test_grade_and_write_upgrades_legacy_file_header_on_disk(tmp_path):
    """End-to-end: read a v3 file, write it straight back via
    _atomic_write_rows (exactly what _grade_one_log does), and confirm the
    on-disk header is now canonical -- the actual production fix, not just
    an in-memory shape."""
    from grade_picks import _read_rows_locked, _atomic_write_rows

    log = tmp_path / "pick_log_manual.csv"
    _write_v3_log(log, [
        {"date": "2026-04-19", "player": "Test A", "stat": "AST", "line": "6.5",
         "direction": "over", "odds": "-110", "book": "fanduel", "size": "1.00",
         "result": "W"},
        {"date": "2026-04-20", "player": "Test B", "stat": "PTS", "line": "22.5",
         "direction": "under", "odds": "+100", "book": "draftkings", "size": "1.00",
         "result": ""},
    ])

    rows, fieldnames = _read_rows_locked(log)
    _atomic_write_rows(log, fieldnames, rows, lock_timeout=5)

    with open(log, newline="", encoding="utf-8") as f:
        reread = csv.DictReader(f)
        on_disk_header = reread.fieldnames
        reread_rows = list(reread)

    assert list(on_disk_header) == list(CANONICAL_HEADER)
    assert len(reread_rows) == 2
    assert reread_rows[0]["result"] == "W"
    assert reread_rows[0]["player"] == "Test A"
    assert reread_rows[1]["result"] == ""


def test_read_rows_locked_v6_canonical_log_unaffected(tmp_path):
    """A log already at the current schema must read back byte-identical in
    content -- migration must be a no-op for already-canonical data, not
    just tolerant of it."""
    from grade_picks import _read_rows_locked

    log = tmp_path / "pick_log.csv"
    row = {c: "" for c in CANONICAL_HEADER}
    row.update({"date": "2026-04-19", "player": "Test A", "stat": "AST",
                "line": "6.5", "direction": "over", "odds": "-110",
                "book": "fanduel", "size": "1.00", "result": "W",
                "source": "sabersim", "model_version": "v7", "run_id": "abc123"})
    _write_canonical_log(log, [row])

    rows, fieldnames = _read_rows_locked(log)

    assert len(rows) == 1
    assert rows[0]["result"] == "W"
    assert rows[0]["source"] == "sabersim"
    assert rows[0]["model_version"] == "v7"
    assert rows[0]["run_id"] == "abc123"
    assert list(fieldnames) == list(CANONICAL_HEADER)


def test_read_rows_locked_still_aborts_on_lock_timeout(tmp_path, monkeypatch):
    """The fix must not weaken grade_picks' existing hard-abort-on-timeout
    contract (real-money grading path) by silently adopting pick_log_io's
    softer warn-and-continue default."""
    import grade_picks

    log = tmp_path / "pick_log.csv"
    _write_canonical_log(log, [{"date": "2026-04-19", "result": "W"}])

    class _AlwaysTimesOut:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            raise grade_picks.FileLockTimeout(str(log) + ".lock")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(grade_picks, "FileLock", _AlwaysTimesOut)

    with pytest.raises(RuntimeError, match="aborting to avoid stale/partial data"):
        grade_picks._read_rows_locked(log, lock_timeout=1)


# ─────────────────────────────────────────────────────────────────
# T2 (R3) — run_picks.py manual-entry writer column completeness
# ─────────────────────────────────────────────────────────────────

def _manual_row_via_dictwriter_fix(log_path, **overrides):
    """Mirrors exactly what the fixed --log-manual block should write:
    a full canonical-shaped dict through DictWriter(fieldnames=CANONICAL_HEADER).
    Used to pre-validate the target shape before wiring it into run_picks.py's
    interactive flow (which isn't directly unit-testable -- it reads stdin)."""
    from pick_log_schema import normalize_is_home, normalize_size

    row = {c: "" for c in CANONICAL_HEADER}
    row.update({
        "date": "2026-04-19", "run_time": "14:05", "run_type": "manual",
        "sport": "NBA", "player": "Test Player", "team": "BOS",
        "stat": "PTS", "line": "24.5", "direction": "over",
        "odds": "+105", "book": "fanduel", "tier": "MANUAL",
        "size": normalize_size("1.25"), "game": "Boston Celtics @ Miami Heat",
        "mode": "Default", "is_home": normalize_is_home("", "PTS"),
    })
    row.update(overrides)

    write_header = not log_path.exists() or log_path.stat().st_size == 0
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return row


def test_manual_entry_target_shape_populates_all_canonical_columns(tmp_path):
    """Pre-registers the exact target behavior for the run_picks.py fix:
    every CANONICAL_HEADER column -- including the 4 that the old 29-value
    positional list silently dropped -- must be present after a manual
    write, even if blank."""
    log = tmp_path / "pick_log_manual.csv"
    _manual_row_via_dictwriter_fix(log)

    with open(log, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == list(CANONICAL_HEADER)
        rows = list(reader)

    assert len(rows) == 1
    for col in ("source", "model_version", "run_id", "clv_corrected"):
        assert col in rows[0] and rows[0][col] == "", (
            f"manual entry must write {col!r} (blank is fine -- absent is the bug)"
        )
    assert rows[0]["player"] == "Test Player"
    assert rows[0]["odds"] == "+105"


def test_run_picks_log_manual_block_no_longer_uses_positional_writer():
    """Static guard: the fixed source must not contain a bare csv.writer
    positional row for the manual-entry path -- DictWriter keyed by
    CANONICAL_HEADER is the only way to make column-count drift structurally
    impossible instead of re-patchable."""
    src = (ENGINE / "run_picks.py").read_text(encoding="utf-8")
    log_manual_ix = src.find("if args.log_manual:")
    assert log_manual_ix > 0, "run_picks.py must have the --log-manual block"
    # Scan to the next top-level "if args." block (repost) as the section end.
    next_section_ix = src.find("if args.repost:", log_manual_ix)
    assert next_section_ix > log_manual_ix
    section = src[log_manual_ix:next_section_ix]
    assert "csv.writer(f)" not in section, (
        "--log-manual must not use positional csv.writer -- use "
        "csv.DictWriter(fieldnames=CANONICAL_HEADER) so column order can "
        "never silently drift from the schema again."
    )
    assert "csv.DictWriter" in section and "CANONICAL_HEADER" in section


def test_run_picks_log_manual_upgrades_legacy_header_on_write():
    """Static guard: the fixed block must detect and upgrade a stale
    on-disk header (mirrors pick_log_writers.log_picks()'s existing
    set(HEADER) != set(old_header) pattern) -- otherwise fixing only the
    append creates a worse mismatch against pick_log_manual.csv's real,
    still-v3, on-disk header."""
    src = (ENGINE / "run_picks.py").read_text(encoding="utf-8")
    log_manual_ix = src.find("if args.log_manual:")
    next_section_ix = src.find("if args.repost:", log_manual_ix)
    section = src[log_manual_ix:next_section_ix]
    assert "CANONICAL_HEADER" in section and (
        "set(CANONICAL_HEADER)" in section or "set(HEADER)" in section
    ), (
        "--log-manual must detect on-disk header drift against "
        "CANONICAL_HEADER and rewrite the file, mirroring log_picks()'s "
        "existing upgrade-on-write pattern."
    )


def test_run_picks_log_manual_upgrade_uses_canonical_migrate_row():
    """Static guard: the header-upgrade rewrite must migrate existing rows
    through the canonical migrate_row() helper (already imported in this
    file as _migrate_pick_row) rather than passing raw on-disk dicts
    straight to DictWriter -- guarantees every rewritten row is genuinely
    canonical-shaped, not just however DictWriter's restval happens to
    fill gaps."""
    src = (ENGINE / "run_picks.py").read_text(encoding="utf-8")
    log_manual_ix = src.find("if args.log_manual:")
    next_section_ix = src.find("if args.repost:", log_manual_ix)
    section = src[log_manual_ix:next_section_ix]
    assert "_migrate_pick_row(" in section, (
        "--log-manual's header-upgrade path must migrate existing rows "
        "through _migrate_pick_row (pick_log_schema.migrate_row) before "
        "rewriting them under the canonical header."
    )


def test_run_picks_log_manual_writes_all_four_provenance_columns():
    """The manual row dict must be seeded from every CANONICAL_HEADER
    column -- not just the 4 the old positional list happened to drop.
    Seeding via a comprehension over CANONICAL_HEADER (rather than 4
    hardcoded literal keys) is a strictly stronger guarantee: it covers
    source/model_version/run_id/clv_corrected today AND any future schema
    bump automatically, with zero chance of repeating this exact bug."""
    src = (ENGINE / "run_picks.py").read_text(encoding="utf-8")
    log_manual_ix = src.find("if args.log_manual:")
    next_section_ix = src.find("if args.repost:", log_manual_ix)
    section = src[log_manual_ix:next_section_ix]
    assert "for c in CANONICAL_HEADER" in section or all(
        col in section for col in
        ('"source"', '"model_version"', '"run_id"', '"clv_corrected"')
    ), (
        "--log-manual's row dict must be fully seeded from CANONICAL_HEADER "
        "(comprehension) or explicitly key all 4 provenance columns — "
        "either way, source/model_version/run_id/clv_corrected must never "
        "be silently absent again."
    )
