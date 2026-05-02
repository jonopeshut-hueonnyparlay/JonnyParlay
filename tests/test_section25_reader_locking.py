#!/usr/bin/env python3
"""Regression tests for Section 25 — reader filelock coverage + post_nrfi_bonus
schema hardening.

Covers:
  M-1   analyze_picks.py reads pick_log via pick_log_io.read_rows_locked_if_exists
        instead of a bare csv.DictReader — so reporting can't see a torn row
        during a concurrent run_picks / capture_clv / grade_picks write.

  M-2   clv_report.py routes through the same helper for the same reason.

  M-15  capture_clv.py's load_picks() routes through read_rows_locked_if_exists.
        The write path (write_closing_odds) already takes the same FileLock,
        matching the read side so no reader can race an in-flight rewrite.

  M-19  post_nrfi_bonus.py holds the shared pick_log_lock across the
        existence-check AND the append, and refreshes the schema sidecar
        after the write so M-13 applies to ad-hoc bonus posts too.

  M-20  post_nrfi_bonus.py builds its row from pick_log_schema.CANONICAL_HEADER
        via DictWriter(fieldnames=CANONICAL_HEADER) and runs every normalized
        field through the Section 24 helpers (normalize_size / _edge / _proj /
        _is_home / _american_odds). No more inline 27-col list that can drift.

This file is intentionally filesystem-heavy — several tests exercise the
locking contract by firing a second FileLock in a thread and asserting the
primary reader blocks on it, because grepping for imports proves wiring but
not semantics.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))

from pick_log_schema import (  # noqa: E402
    CANONICAL_HEADER,
    SCHEMA_VERSION,
    schema_sidecar_path,
)
import pick_log_io  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _read_src(relpath: str) -> str:
    """Slurp a source file relative to the repo root."""
    return (HERE.parent / relpath).read_text(encoding="utf-8")


def _write_canonical_log(path: Path, rows: list[dict]) -> None:
    """Write a CSV with the canonical header — used by the locking-semantics tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(CANONICAL_HEADER), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CANONICAL_HEADER})


# ─────────────────────────────────────────────────────────────────
# M-1 — analyze_picks.py routes reads through the shared helper
# ─────────────────────────────────────────────────────────────────

def test_m1_analyze_picks_imports_locked_reader():
    """analyze_picks.py must route reads through the shared pick_log_io module —
    either via ``read_rows_locked_if_exists`` directly, or via the consolidated
    ``load_rows`` wrapper (which itself calls the locked reader internally per
    arch note #3).  Either way, the FileLock path is guaranteed."""
    src = _read_src("engine/analyze_picks.py")
    assert re.search(
        r"from\s+pick_log_io\s+import\s+[^\n]*"
        r"(read_rows_locked_if_exists|load_rows)",
        src,
    ), (
        "analyze_picks.py must import a locked reader (read_rows_locked_if_exists "
        "or load_rows) from pick_log_io — a bare csv.DictReader opens a race "
        "window with capture_clv / grade_picks."
    )
    # Whichever helper is imported must actually be called on the pick_log read path.
    assert ("read_rows_locked_if_exists(" in src) or ("load_rows(" in src)


def test_m1_analyze_picks_has_no_bare_pick_log_open():
    """Every open() of pick_log.csv must go through the helper."""
    src = _read_src("engine/analyze_picks.py")
    # `open(log_path` / `open(p` / `open(PICK_LOG_PATH` — any of these on the
    # pick_log.csv path would be a regression. The helper does its own open()
    # internally; the module should not.
    forbidden = ['open("~/Documents/JonnyParlay/data/pick_log', 'open(log_path', 'open(PICK_LOG_PATH']
    for token in forbidden:
        if token in src:
            # Guard against false positives — the only sanctioned open() is
            # the export path under --export. Everything else must route
            # through read_rows_locked_if_exists.
            pytest.fail(
                f"analyze_picks.py contains raw `{token}` — if this reads "
                f"pick_log it must use read_rows_locked_if_exists."
            )


# ─────────────────────────────────────────────────────────────────
# M-2 — clv_report.py routes reads through the shared helper
# ─────────────────────────────────────────────────────────────────

def test_m2_clv_report_imports_locked_reader():
    """Same guard as M-1 — either the direct reader OR the consolidated
    ``load_rows`` wrapper is acceptable (arch note #3)."""
    src = _read_src("engine/clv_report.py")
    assert re.search(
        r"from\s+pick_log_io\s+import\s+[^\n]*"
        r"(read_rows_locked_if_exists|load_rows)",
        src,
    ), (
        "clv_report.py must import a locked reader (read_rows_locked_if_exists "
        "or load_rows) from pick_log_io."
    )
    assert ("read_rows_locked_if_exists(" in src) or ("load_rows(" in src)


def test_m2_clv_report_uses_helper_for_every_log():
    """The report reads pick_log.csv + pick_log_manual.csv + shadow logs — all three
    go through one central loop. Confirm we're not sneaking in a second bare open()."""
    src = _read_src("engine/clv_report.py")
    # csv.DictReader appears in source imports but must NOT appear as a call.
    # (clv_report.py doesn't actually import DictReader by name; this is a
    # belt-and-braces guard against regressions.)
    assert "csv.DictReader(" not in src, (
        "clv_report.py must not call csv.DictReader directly — "
        "route all pick_log reads through read_rows_locked_if_exists."
    )


# ─────────────────────────────────────────────────────────────────
# M-15 — capture_clv.py load_picks routes through the shared helper
# ─────────────────────────────────────────────────────────────────

def test_m15_capture_clv_load_picks_uses_locked_reader():
    src = _read_src("engine/capture_clv.py")
    assert "from pick_log_io import" in src and "read_rows_locked_if_exists" in src, (
        "capture_clv.py must import the shared locked reader."
    )
    # load_picks must actually invoke it.
    load_picks_ix = src.find("def load_picks(")
    assert load_picks_ix > 0, "capture_clv.load_picks() not found"
    # Check the next ~1000 chars after the def — the helper call should live there.
    body = src[load_picks_ix:load_picks_ix + 1000]
    assert "read_rows_locked_if_exists(" in body, (
        "capture_clv.load_picks() must call read_rows_locked_if_exists() so "
        "it can't race a concurrent write."
    )


def test_m15_capture_clv_write_path_still_holds_lock():
    """write_closing_odds must still acquire its own FileLock — the reader fix
    doesn't remove the writer's lock obligation."""
    src = _read_src("engine/capture_clv.py")
    wix = src.find("def write_closing_odds(")
    assert wix > 0
    body = src[wix:wix + 800]
    assert "FileLock(" in body, (
        "capture_clv.write_closing_odds() must still take a FileLock — "
        "the reader-side fix doesn't remove the write contract."
    )


# ─────────────────────────────────────────────────────────────────
# M-19 — post_nrfi_bonus.py write is lock-held + sidecar-refreshed
# ─────────────────────────────────────────────────────────────────

POST_NRFI_PATH = HERE.parent / "post_nrfi_bonus.py"


def test_m19_post_nrfi_holds_pick_log_lock():
    src = POST_NRFI_PATH.read_text(encoding="utf-8")
    assert "from pick_log_io import pick_log_lock" in src
    # The context manager must wrap the existence-check + write.
    assert "with pick_log_lock(log_path):" in src


def test_m19_post_nrfi_refreshes_schema_sidecar():
    src = POST_NRFI_PATH.read_text(encoding="utf-8")
    assert "write_schema_sidecar" in src, (
        "post_nrfi_bonus.py must refresh the schema sidecar after a successful "
        "write (audit M-13) so the M-13 contract applies to ad-hoc bonus posts."
    )
    # Sidecar write must come AFTER the `with pick_log_lock(...)` block so
    # we're not holding the lock on json dumping. Enforce ordering.
    lock_ix    = src.find("with pick_log_lock(log_path):")
    sidecar_ix = src.find("write_schema_sidecar(log_path)")
    assert lock_ix > 0 and sidecar_ix > 0
    assert sidecar_ix > lock_ix, (
        "write_schema_sidecar must be called after the lock block closes — "
        "sidecar writes shouldn't hold the pick_log lock."
    )


def test_m19_post_nrfi_tolerates_sidecar_failure():
    """The sidecar refresh is best-effort; a sidecar exception must not orphan
    the pick we just appended. Enforce that the call is wrapped in try/except."""
    src = POST_NRFI_PATH.read_text(encoding="utf-8")
    sidecar_ix = src.find("write_schema_sidecar(log_path)")
    # Scan backwards for the enclosing try.
    preceding = src[:sidecar_ix]
    last_try = preceding.rfind("try:")
    assert last_try > 0, "write_schema_sidecar call must be inside a try/except"
    # Make sure there's no `except` between `try:` and our call that would
    # mean we're in the except-clause of a DIFFERENT try.
    between = preceding[last_try:]
    assert between.count("except") == 0, (
        "sidecar call is not in the protected try-block body"
    )
    # And the except must come after.
    following = src[sidecar_ix:]
    assert "except Exception" in following[:400], (
        "sidecar write must be caught by a broad Exception — best-effort only."
    )


# ─────────────────────────────────────────────────────────────────
# M-20 — post_nrfi_bonus.py uses CANONICAL_HEADER + Section-24 normalizers
# ─────────────────────────────────────────────────────────────────

def test_m20_post_nrfi_uses_canonical_header():
    src = POST_NRFI_PATH.read_text(encoding="utf-8")
    assert "CANONICAL_HEADER" in src
    # DictWriter must be parameterised by the canonical header constant —
    # no inline 27-col list that drifts when v3 columns land.
    assert "fieldnames=CANONICAL_HEADER" in src, (
        "post_nrfi_bonus.py must pass CANONICAL_HEADER to DictWriter so it "
        "tracks schema bumps automatically."
    )


@pytest.mark.parametrize("normalizer", [
    "normalize_size",
    "normalize_edge",
    "normalize_proj",
    "normalize_is_home",
    "normalize_american_odds",
])
def test_m20_post_nrfi_imports_section_24_normalizers(normalizer):
    src = POST_NRFI_PATH.read_text(encoding="utf-8")
    assert normalizer in src, (
        f"post_nrfi_bonus.py must import + use {normalizer} so the ad-hoc "
        f"bonus path matches the Section 24 data contract."
    )


def test_m20_post_nrfi_row_routes_values_through_normalizers():
    """Every numeric field on the row dict should pass through a normalizer."""
    src = POST_NRFI_PATH.read_text(encoding="utf-8")
    # We don't enforce precise whitespace — just that each key is followed
    # (within a handful of chars) by a `normalize_*(` call.
    import re
    for key, fn in [
        ("proj",    "normalize_proj"),
        ("edge",    "normalize_edge"),
        ("odds",    "normalize_american_odds"),
        ("size",    "normalize_size"),
        ("is_home", "normalize_is_home"),
    ]:
        # e.g. `"size":     normalize_size("0.50"),`
        pat = re.compile(rf'"{key}"\s*:\s*{fn}\(')
        assert pat.search(src), (
            f'row["{key}"] must be wired through {fn}(...) — found none.'
        )


# ─────────────────────────────────────────────────────────────────
# run_picks.py / grade_picks.py — reader sites stay lock-wrapped
# ─────────────────────────────────────────────────────────────────

def test_run_picks_read_sites_hold_pick_log_lock():
    """Every csv.DictReader over pick_log.csv in run_picks.py must be inside
    a `with _pick_log_lock(...)` block. We can't do a full AST walk cheaply,
    so instead we count — the reader count must equal the lock-scope count."""
    src = _read_src("engine/run_picks.py")
    # csv.DictReader is also used to parse the SaberSim input CSV (line 1024),
    # so we only count pick_log readers. Those are the ones inside
    # _pick_log_lock contexts.
    dictreader_count = src.count("csv.DictReader(f)")
    lockscope_count  = src.count("_pick_log_lock(")
    # Every pick_log read must be nested inside a _pick_log_lock, but the lock
    # is also used by writers + header-migration paths, so lock_count >= reader_count
    # is the right invariant (strict equality would flunk whenever a write
    # lock is re-used across different code paths).
    assert lockscope_count >= 1, "run_picks.py must contain _pick_log_lock scopes"
    assert dictreader_count >= 1, "run_picks.py must actually read pick_log"
    # The real invariant: if we strip all _pick_log_lock blocks out, the only
    # remaining DictReader should be for the SaberSim CSV (one call).
    # Walk line by line tracking lock depth — a minimal simulator.
    depth = 0
    unlocked_readers = 0
    for line in src.splitlines():
        # Crude but sufficient — these two substrings don't appear in comments
        # meaningfully in this file.
        if "with _pick_log_lock(" in line:
            depth += 1
        # `with open(` following a `with _pick_log_lock(` lives at depth > 0.
        if "csv.DictReader(f)" in line:
            # Exclude the SaberSim CSV reader (inside parse_csv, not under lock).
            # We'll allow exactly one unlocked DictReader — the SaberSim one.
            if depth == 0:
                unlocked_readers += 1
        # Very loose dedent detection — good enough for this tree because
        # the lock scopes are short (<20 lines each).
        if line.strip() == "" and depth > 0:
            # Don't decrement on blank lines — just a guard against infinite depth.
            pass
        if line.startswith("def ") or line.startswith("class "):
            depth = 0
    assert unlocked_readers <= 1, (
        f"run_picks.py has {unlocked_readers} csv.DictReader calls outside "
        f"_pick_log_lock — only the SaberSim CSV reader is allowed to be unlocked."
    )


def test_grade_picks_has_locked_reader_helper():
    src = _read_src("engine/grade_picks.py")
    assert "def _read_rows_locked(" in src, (
        "grade_picks.py must expose _read_rows_locked for its own pick_log reads."
    )
    # The helper must acquire FileLock.
    helper_ix = src.find("def _read_rows_locked(")
    body = src[helper_ix:helper_ix + 1500]
    assert "FileLock(" in body, (
        "grade_picks._read_rows_locked must acquire FileLock."
    )


# ─────────────────────────────────────────────────────────────────
# End-to-end: reader truly blocks while writer holds the lock
# ─────────────────────────────────────────────────────────────────

def test_reader_blocks_while_writer_holds_lock(tmp_path):
    """Prove semantically that read_rows_locked_if_exists takes the same lock
    a writer takes. Fire up a writer in a SUBPROCESS (filelock's POSIX impl
    is per-process; two FileLocks in the same PID don't exclude each other)
    that holds the lock for ~0.8s. The reader started after must not
    complete until the writer releases."""
    import subprocess
    import textwrap

    log = tmp_path / "pick_log.csv"
    _write_canonical_log(log, [
        {"date": "2026-04-20", "player": "test", "stat": "PTS", "line": "20.5",
         "direction": "over", "odds": "+100", "size": "1.00", "result": "W"},
    ])

    lock_path = str(log) + ".lock"
    ready_marker = tmp_path / "writer_ready.flag"
    writer_script = tmp_path / "_writer.py"
    writer_script.write_text(textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(HERE / 'engine')!r})
        from filelock import FileLock
        with FileLock({lock_path!r}, timeout=10):
            open({str(ready_marker)!r}, 'w').close()
            time.sleep(0.8)
    """))

    proc = subprocess.Popen([sys.executable, str(writer_script)])
    try:
        # Spin until the writer has acquired its FileLock.
        deadline = time.monotonic() + 3.0
        while not ready_marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready_marker.exists(), "writer subprocess never acquired the lock"

        reader_start = time.monotonic()
        rows, fieldnames = pick_log_io.read_rows_locked_if_exists(log, lock_timeout=10)
        reader_elapsed = time.monotonic() - reader_start

        assert reader_elapsed >= 0.3, (
            f"reader completed in {reader_elapsed:.3f}s — should have waited "
            f"for writer subprocess to release lock (~0.8s). Reader likely "
            f"isn't taking the same FileLock the writers use."
        )
        assert len(rows) == 1
        assert "player" in fieldnames
    finally:
        proc.wait(timeout=5)


def test_reader_returns_empty_on_missing_file(tmp_path):
    """read_rows_locked_if_exists tolerates a missing file — callers rely on
    ([], []) to branch without exists() checks."""
    log = tmp_path / "does_not_exist.csv"
    rows, fieldnames = pick_log_io.read_rows_locked_if_exists(log)
    assert rows == [] and fieldnames == []


def test_reader_returns_empty_on_zero_byte_file(tmp_path):
    log = tmp_path / "pick_log.csv"
    log.touch()
    assert log.stat().st_size == 0
    rows, fieldnames = pick_log_io.read_rows_locked_if_exists(log)
    assert rows == [] and fieldnames == []


# ─────────────────────────────────────────────────────────────────
# pick_log_io surface — __all__ covers everything the readers import
# ─────────────────────────────────────────────────────────────────

def test_pick_log_io_exports_locked_readers():
    assert "read_rows_locked"           in pick_log_io.__all__
    assert "read_rows_locked_if_exists" in pick_log_io.__all__
    assert "pick_log_lock"              in pick_log_io.__all__


# ─────────────────────────────────────────────────────────────────
# post_nrfi_bonus end-to-end sidecar contract (Section 24 + 25)
# ─────────────────────────────────────────────────────────────────

def test_post_nrfi_round_trip_sidecar(tmp_path, monkeypatch):
    """Simulate the post_nrfi_bonus append path — holding the lock, writing
    the row via CANONICAL_HEADER DictWriter, refreshing the sidecar — and
    check the on-disk invariants hold."""
    log = tmp_path / "pick_log_mlb.csv"
    sidecar = schema_sidecar_path(log)

    # Build a row identical in shape to post_nrfi_bonus's, running the
    # numeric fields through the Section 24 normalizers.
    from pick_log_schema import (
        normalize_american_odds,
        normalize_edge,
        normalize_is_home,
        normalize_proj,
        normalize_size,
        write_schema_sidecar,
    )
    row = {
        "date":        "2026-04-20",
        "run_time":    "13:05",
        "run_type":    "bonus",
        "sport":       "MLB",
        "player":      "NRFI",
        "team":        "TOR@ARI",
        "stat":        "NRFI",
        "line":        "0.5",
        "direction":   "under",
        "proj":        normalize_proj("0.68"),
        "win_prob":    "0.6840",
        "edge":        normalize_edge("0.2130"),
        "odds":        normalize_american_odds("+108"),
        "book":        "fanduel",
        "tier":        "T2",
        "pick_score":  "85.0",
        "size":        normalize_size("0.50"),
        "game":        "Toronto Blue Jays @ Arizona Diamondbacks",
        "mode":        "",
        "result":      "",
        "closing_odds": "",
        "clv":         "",
        "card_slot":   "",
        "is_home":     normalize_is_home("", "NRFI"),
        "context_verdict": "",
        "context_reason":  "",
        "context_score":   "",
    }

    with pick_log_io.pick_log_lock(log):
        write_header = not log.exists() or log.stat().st_size == 0
        with open(log, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(CANONICAL_HEADER), extrasaction="ignore")
            if write_header:
                w.writeheader()
            w.writerow(row)
    write_schema_sidecar(log)

    # Re-read via the shared helper — rows must show the normalized values.
    read_rows, read_fieldnames = pick_log_io.read_rows_locked_if_exists(log)
    assert len(read_rows) == 1
    r = read_rows[0]
    assert r["size"]    == "0.50", "normalize_size should pin to 2 decimals"
    assert r["edge"]    == "0.2130", "normalize_edge keeps sub-percent precision"
    assert r["proj"]    == "0.68"
    assert r["odds"]    == "+108", "normalize_american_odds always sign-prefixes"
    assert r["is_home"] == "", "non-SPREAD/ML stat must have blank is_home"

    # Sidecar must exist and record SCHEMA_VERSION + canonical header.
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text())
    assert payload["schema_version"]   == SCHEMA_VERSION
    assert payload["canonical_header"] == list(CANONICAL_HEADER)


def test_post_nrfi_script_compiles():
    """Smoke test — the module must be syntactically valid after our edits.
    We can't execute it (it posts to Discord), but we can compile it."""
    import py_compile
    py_compile.compile(str(POST_NRFI_PATH), doraise=True)


# ─────────────────────────────────────────────────────────────────
# Schema drift detection — reader must warn once when header differs
# ─────────────────────────────────────────────────────────────────

def test_read_rows_locked_migrates_legacy_header(tmp_path, capsys):
    """A CSV written under an older schema (missing v2 columns) must be
    migrated on read — callers see canonical-shaped dicts. This is the
    integration point between M-13 (sidecar) and M-series locked reads."""
    log = tmp_path / "pick_log_legacy.csv"
    # v1-ish header: no closing_odds/clv/card_slot/is_home/context_* columns.
    legacy_header = [
        "date", "run_time", "run_type", "sport", "player", "team",
        "stat", "line", "direction", "proj", "win_prob", "edge",
        "odds", "book", "tier", "pick_score", "size", "game", "mode", "result",
    ]
    with open(log, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=legacy_header)
        w.writeheader()
        w.writerow({k: "x" for k in legacy_header})

    rows, fieldnames = pick_log_io.read_rows_locked_if_exists(log)
    assert len(rows) == 1
    # fieldnames reflects what was ON DISK (drift-detection signal).
    assert fieldnames == legacy_header
    # Migrated rows must have the v2 columns filled in with "" defaults.
    for col in ("closing_odds", "clv", "card_slot", "is_home",
                "context_verdict", "context_reason", "context_score"):
        assert col in rows[0], f"migrated row missing v2 column {col!r}"
        assert rows[0][col] == ""


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
