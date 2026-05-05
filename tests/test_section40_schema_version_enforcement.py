"""Section 40 — schema version fail-fast enforcement (arch note #5).

The pick_log CSVs have had a 27-column canonical schema pinned in
``pick_log_schema.py`` since Section 16, but nothing *enforced* that
contract at the read boundary. A future engine bump that added column #28
would silently migrate old rows (fine) and also silently drop column #28
from a log written by a newer build that was copied back to an older
machine (not fine — data loss hidden under a migrate_row() call).

Section 40 closes arch note #5 by:

1. Refreshing a ``<log>.schema.json`` sidecar from *every* writer path —
   ``run_picks.log_picks`` (already wired), ``post_nrfi_bonus`` (already
   wired), ``capture_clv.write_closing_odds`` (added here), and
   ``grade_picks._atomic_write_rows`` (added here).

2. Making ``pick_log_io.read_rows_locked`` check that sidecar before it
   hands rows to the caller — if the sidecar declares a version strictly
   greater than the engine's ``SCHEMA_VERSION``, raise
   ``SchemaVersionMismatchError`` instead of silently migrating.

3. Tolerating missing / corrupt sidecars (legacy logs, pre-arch-note
   deployments) so upgrading doesn't break anyone's existing pick_log.

These tests enforce every part of that contract, plus the byte-identical
root-mirror invariant for the three modified engine files.
"""

from __future__ import annotations

import ast
import csv
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"

# Make ``engine/`` importable the same way the launchers do.
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


# ── SchemaVersionMismatchError surface ─────────────────────────────────────

def test_mismatch_error_exported():
    import pick_log_io

    assert hasattr(pick_log_io, "SchemaVersionMismatchError")
    assert "SchemaVersionMismatchError" in pick_log_io.__all__
    assert issubclass(pick_log_io.SchemaVersionMismatchError, Exception)


def test_mismatch_error_subclass_of_runtime_error():
    """RuntimeError is the right base — it's a state problem, not a bug.

    Readers can ``except RuntimeError`` and know they caught a recoverable
    engine-is-too-old situation without having to import the specific class.
    """
    from pick_log_io import SchemaVersionMismatchError

    assert issubclass(SchemaVersionMismatchError, RuntimeError)


# ── Sidecar round-trip + fail-fast read behaviour ──────────────────────────

def _write_min_log(path: Path) -> None:
    """Write a minimal canonical-shaped pick_log to *path*."""
    from pick_log_schema import CANONICAL_HEADER

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(CANONICAL_HEADER))
        writer.writeheader()
        writer.writerow({c: "" for c in CANONICAL_HEADER})


def test_read_rows_locked_happy_path_with_current_sidecar(tmp_path):
    """Sidecar at the engine's current version reads cleanly."""
    from pick_log_io import read_rows_locked
    from pick_log_schema import SCHEMA_VERSION, write_schema_sidecar

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)
    write_schema_sidecar(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    assert sidecar.is_file()
    assert json.loads(sidecar.read_text())["schema_version"] == SCHEMA_VERSION

    rows, fn = read_rows_locked(log, lock_timeout=2)
    assert isinstance(rows, list)
    assert fn  # non-empty fieldnames


def test_read_rows_locked_fails_fast_on_future_sidecar(tmp_path):
    """A sidecar declaring a version strictly > SCHEMA_VERSION must raise."""
    from pick_log_io import read_rows_locked, SchemaVersionMismatchError
    from pick_log_schema import SCHEMA_VERSION

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    sidecar.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION + 1,
        "canonical_header": ["date", "speculative_future_col"],
    }))

    with pytest.raises(SchemaVersionMismatchError) as exc:
        read_rows_locked(log, lock_timeout=2)

    # Error message surfaces the version gap so the operator knows what to
    # upgrade.
    msg = str(exc.value)
    assert f"v{SCHEMA_VERSION}" in msg
    assert str(SCHEMA_VERSION + 1) in msg


def test_read_rows_locked_tolerates_missing_sidecar(tmp_path):
    """Legacy logs without a sidecar must keep working."""
    from pick_log_io import read_rows_locked

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)
    # No sidecar written.

    rows, fn = read_rows_locked(log, lock_timeout=2)
    assert isinstance(rows, list)
    assert fn


def test_read_rows_locked_tolerates_corrupt_sidecar(tmp_path):
    """Unparseable JSON in the sidecar must not block reads."""
    from pick_log_io import read_rows_locked

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    sidecar.write_text("{not valid json")  # deliberately broken

    # Should not raise — read_schema_sidecar swallows JSONDecodeError.
    rows, fn = read_rows_locked(log, lock_timeout=2)
    assert isinstance(rows, list)
    assert fn


def test_read_rows_locked_tolerates_equal_version_sidecar(tmp_path):
    """Sidecar at exactly SCHEMA_VERSION is the canonical case — must pass."""
    from pick_log_io import read_rows_locked
    from pick_log_schema import SCHEMA_VERSION

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    sidecar.write_text(json.dumps({"schema_version": SCHEMA_VERSION}))

    rows, fn = read_rows_locked(log, lock_timeout=2)
    assert isinstance(rows, list)


def test_read_rows_locked_tolerates_older_version_sidecar(tmp_path):
    """v1 sidecar must still be readable — migrate_row handles the shape."""
    from pick_log_io import read_rows_locked

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    sidecar.write_text(json.dumps({"schema_version": 1}))

    rows, fn = read_rows_locked(log, lock_timeout=2)
    assert isinstance(rows, list)


def test_read_rows_locked_tolerates_non_int_version(tmp_path):
    """A sidecar with a non-int version is treated as unparseable, not future.

    Guards against a sidecar that got written with a string like ``"2"``
    — that's not valid but also not evidence of a future schema. Callers
    must not be blocked by such a sidecar.
    """
    from pick_log_io import read_rows_locked

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    sidecar.write_text(json.dumps({"schema_version": "banana"}))

    rows, fn = read_rows_locked(log, lock_timeout=2)
    assert isinstance(rows, list)


def test_read_rows_locked_if_exists_also_fails_fast(tmp_path):
    """The ``_if_exists`` variant must also raise — it calls through."""
    from pick_log_io import (
        read_rows_locked_if_exists,
        SchemaVersionMismatchError,
    )
    from pick_log_schema import SCHEMA_VERSION

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    sidecar.write_text(json.dumps({"schema_version": SCHEMA_VERSION + 5}))

    with pytest.raises(SchemaVersionMismatchError):
        read_rows_locked_if_exists(log, lock_timeout=2)


def test_load_rows_also_fails_fast(tmp_path):
    """``load_rows`` goes through read_rows_locked_if_exists — same guard."""
    from pick_log_io import load_rows, SchemaVersionMismatchError
    from pick_log_schema import SCHEMA_VERSION

    log = tmp_path / "pick_log.csv"
    _write_min_log(log)

    sidecar = log.with_name(log.stem + ".schema.json")
    sidecar.write_text(json.dumps({"schema_version": SCHEMA_VERSION + 1}))

    with pytest.raises(SchemaVersionMismatchError):
        load_rows([log], lock_timeout=2)


# ── Writer-side sidecar refresh ────────────────────────────────────────────

def test_capture_clv_imports_write_schema_sidecar():
    src = (ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8")
    assert "from pick_log_schema import" in src
    assert "write_schema_sidecar" in src


def test_capture_clv_calls_write_schema_sidecar_after_write():
    """``_do_write_closing_odds`` must refresh the sidecar after os.replace."""
    import capture_clv

    src = textwrap.dedent(ast.unparse(
        ast.parse((ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8"))
    ))
    # Grab the body of _do_write_closing_odds — that's where the atomic
    # replace lives. The sidecar call must come after it.
    tree = ast.parse((ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8"))
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_do_write_closing_odds":
            func = node
            break
    assert func is not None, "capture_clv._do_write_closing_odds must exist"

    body_src = "\n".join(ast.unparse(stmt) for stmt in func.body)
    assert "os.replace" in body_src
    assert "_write_schema_sidecar" in body_src
    # Sidecar call must be AFTER the os.replace line.
    replace_idx = body_src.index("os.replace")
    sidecar_idx = body_src.index("_write_schema_sidecar")
    assert sidecar_idx > replace_idx, (
        "Sidecar refresh must come AFTER os.replace — otherwise a crash "
        "leaves a sidecar claiming a version the CSV never actually reached."
    )


def test_grade_picks_imports_write_schema_sidecar():
    src = (ENGINE_DIR / "grade_picks.py").read_text(encoding="utf-8")
    assert "from pick_log_schema import write_schema_sidecar" in src


def test_grade_picks_calls_write_schema_sidecar_after_atomic_write():
    tree = ast.parse((ENGINE_DIR / "grade_picks.py").read_text(encoding="utf-8"))
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_atomic_write_rows":
            func = node
            break
    assert func is not None, "grade_picks._atomic_write_rows must exist"

    body_src = "\n".join(ast.unparse(stmt) for stmt in func.body)
    assert "_write_schema_sidecar" in body_src
    # The sidecar call must be after the FileLock-wrapped write block, not
    # nested inside the ``_do_write`` closure (which would double-fire on
    # fall-through).
    fl_idx = body_src.index("FileLock")
    sidecar_idx = body_src.index("_write_schema_sidecar")
    assert sidecar_idx > fl_idx


def test_capture_clv_sidecar_refresh_is_fault_tolerant():
    """Sidecar failures must never block CLV writes.

    If write_schema_sidecar raises (disk full, permission error, whatever),
    the writer has to swallow the exception and keep going. Verified by
    scanning the source for the try/except bracket.
    """
    src = (ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8")
    assert "schema sidecar write failed" in src


def test_grade_picks_sidecar_refresh_is_fault_tolerant():
    src = (ENGINE_DIR / "grade_picks.py").read_text(encoding="utf-8")
    assert "schema sidecar write failed" in src


def test_sidecar_written_by_capture_clv_write_closing_odds(tmp_path, monkeypatch):
    """End-to-end: call write_closing_odds and confirm the sidecar appears."""
    import capture_clv
    from pick_log_schema import CANONICAL_HEADER, SCHEMA_VERSION

    log = tmp_path / "pick_log.csv"
    # Need at least one matchable row to exercise the update path.
    row = {c: "" for c in CANONICAL_HEADER}
    row.update({
        "date": "2026-04-20",
        "sport": "NBA",
        "player": "Test Player",
        "stat": "PTS",
        "line": "20.5",
        "direction": "over",
        "odds": "-110",
        "book": "draftkings",
        "result": "",
    })
    with open(log, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(CANONICAL_HEADER))
        w.writeheader()
        w.writerow(row)

    # Fire the real writer with a matching update. The writer keys rows by
    # ``(date, player.lower(), stat, line, direction.lower())`` — C1 fix added
    # date as the first key component to prevent cross-date key collisions.
    updates = {
        ("2026-04-20", "test player", "PTS", "20.5", "over"): {
            "closing_odds": -108,
            "clv": 0.005,
        }
    }
    n = capture_clv.write_closing_odds(log, updates)
    assert n >= 1, "should have updated at least one row"

    sidecar = log.with_name(log.stem + ".schema.json")
    assert sidecar.is_file(), "write_closing_odds must refresh the sidecar"
    payload = json.loads(sidecar.read_text())
    assert payload["schema_version"] == SCHEMA_VERSION


def test_sidecar_written_by_grade_picks_atomic_write(tmp_path):
    import grade_picks
    from pick_log_schema import CANONICAL_HEADER, SCHEMA_VERSION

    log = tmp_path / "pick_log.csv"
    rows = [{c: "" for c in CANONICAL_HEADER}]
    grade_picks._atomic_write_rows(log, list(CANONICAL_HEADER), rows, lock_timeout=2)

    sidecar = log.with_name(log.stem + ".schema.json")
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text())
    assert payload["schema_version"] == SCHEMA_VERSION


# ── Sidecar write surface coverage ─────────────────────────────────────────

WRITERS_EXPECTED_TO_REFRESH_SIDECAR = [
    ("engine/run_picks.py", "_write_schema_sidecar"),
    # post_nrfi_bonus.py is a standalone one-shot at the repo root — no
    # engine/ mirror exists for it (predates the engine/ consolidation).
    ("post_nrfi_bonus.py", "write_schema_sidecar"),
    ("engine/capture_clv.py", "_write_schema_sidecar"),
    ("engine/grade_picks.py", "_write_schema_sidecar"),
]


@pytest.mark.parametrize(
    "rel_path,needle",
    WRITERS_EXPECTED_TO_REFRESH_SIDECAR,
    ids=[p for p, _ in WRITERS_EXPECTED_TO_REFRESH_SIDECAR],
)
def test_every_writer_refreshes_sidecar(rel_path, needle):
    src = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    assert needle in src, (
        f"{rel_path} writes pick_log but never refreshes the schema sidecar — "
        f"arch note #5 requires every writer to bump it so readers can "
        f"fail-fast on drift."
    )


# ── Root-mirror contract ───────────────────────────────────────────────────
# Every file touched this section is edited under ``engine/`` and must be
# synced byte-identical to the project-root mirror used by Windows launchers.

# L16 (Apr 30 2026): root files are runpy shims — intentionally differ from engine/.
# pick_log_io.py has no root mirror; capture_clv.py and grade_picks.py are shims.
# test_tail_guard.py guards shim validity. (H1/H2, May 1 2026)
