"""Regression tests for Section 31 — log rotation (audit M-24 + M-25).

Covers:
    - engine/log_setup.py public contract (constants, helpers)
    - RotatingFileHandler is actually wired into grade_picks + run_picks loggers
    - preemptive_rotate() behavior (under threshold, over threshold, missing file)
    - Idempotency of attach_rotating_handler (re-imports don't stack handlers)
    - start_clv_daemon.bat contains a preemptive_rotate call before python -u
"""

from __future__ import annotations

import importlib
import logging
import logging.handlers
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"
sys.path.insert(0, str(ENGINE_DIR))


# ── log_setup contract ────────────────────────────────────────────────────────

def test_log_setup_module_importable():
    import log_setup  # noqa: F401
    assert hasattr(log_setup, "attach_rotating_handler")
    assert hasattr(log_setup, "preemptive_rotate")
    assert hasattr(log_setup, "ROTATION_MAX_BYTES")
    assert hasattr(log_setup, "ROTATION_BACKUP_COUNT")


def test_rotation_constants_are_frozen_at_expected_values():
    """Lock the knobs — drift here changes on-disk retention silently."""
    import log_setup
    assert log_setup.ROTATION_MAX_BYTES == 5_000_000
    assert log_setup.ROTATION_BACKUP_COUNT == 5


def test_public_api_list_matches_exports():
    import log_setup
    assert set(log_setup.__all__) == {
        "ROTATION_MAX_BYTES",
        "ROTATION_BACKUP_COUNT",
        "attach_rotating_handler",
        "preemptive_rotate",
    }


# ── attach_rotating_handler ───────────────────────────────────────────────────

def test_attach_rotating_handler_creates_rotating_handler(tmp_path):
    import log_setup
    log_path = tmp_path / "app.log"
    logger = logging.getLogger("test.attach.basic")
    logger.handlers.clear()
    handler = log_setup.attach_rotating_handler(logger, log_path)
    try:
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == log_setup.ROTATION_MAX_BYTES
        assert handler.backupCount == log_setup.ROTATION_BACKUP_COUNT
        assert handler in logger.handlers
    finally:
        logger.handlers.clear()
        handler.close()


def test_attach_rotating_handler_creates_parent_dir(tmp_path):
    import log_setup
    log_path = tmp_path / "nested" / "subdir" / "app.log"
    assert not log_path.parent.exists()
    logger = logging.getLogger("test.attach.mkdir")
    logger.handlers.clear()
    handler = log_setup.attach_rotating_handler(logger, log_path)
    try:
        assert log_path.parent.is_dir()
    finally:
        logger.handlers.clear()
        handler.close()


def test_attach_rotating_handler_is_idempotent_same_path(tmp_path):
    """Calling twice with the same path returns the same handler — no dupes."""
    import log_setup
    log_path = tmp_path / "idem.log"
    logger = logging.getLogger("test.attach.idem")
    logger.handlers.clear()
    h1 = log_setup.attach_rotating_handler(logger, log_path)
    h2 = log_setup.attach_rotating_handler(logger, log_path)
    try:
        assert h1 is h2
        # Only one rotating handler on the logger.
        rotating_handlers = [h for h in logger.handlers
                             if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(rotating_handlers) == 1
    finally:
        logger.handlers.clear()
        h1.close()


def test_attach_rotating_handler_distinct_paths_attach_separately(tmp_path):
    import log_setup
    logger = logging.getLogger("test.attach.distinct")
    logger.handlers.clear()
    h1 = log_setup.attach_rotating_handler(logger, tmp_path / "a.log")
    h2 = log_setup.attach_rotating_handler(logger, tmp_path / "b.log")
    try:
        assert h1 is not h2
        assert len(logger.handlers) == 2
    finally:
        for h in logger.handlers:
            h.close()
        logger.handlers.clear()


def test_attach_rotating_handler_honors_overrides(tmp_path):
    import log_setup
    log_path = tmp_path / "custom.log"
    logger = logging.getLogger("test.attach.custom")
    logger.handlers.clear()
    handler = log_setup.attach_rotating_handler(
        logger, log_path, max_bytes=1000, backup_count=2,
    )
    try:
        assert handler.maxBytes == 1000
        assert handler.backupCount == 2
    finally:
        logger.handlers.clear()
        handler.close()


def test_attach_rotating_handler_actually_rotates_on_size(tmp_path):
    """Behavioral test: write past the threshold, confirm .1 backup appears."""
    import log_setup
    log_path = tmp_path / "roll.log"
    logger = logging.getLogger("test.attach.rollover")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = log_setup.attach_rotating_handler(
        logger, log_path, max_bytes=200, backup_count=3,
    )
    try:
        # Write enough to trigger at least one rollover (each line is ~80 bytes
        # with the formatter prefix).
        for i in range(20):
            logger.info(f"line {i} " + "x" * 60)
        handler.flush()
        assert log_path.exists()
        assert log_path.with_suffix(".log.1").exists(), \
            "RotatingFileHandler did not roll the file to .1 after exceeding max_bytes"
    finally:
        logger.handlers.clear()
        handler.close()


def test_attach_rotating_handler_skips_when_plain_filehandler_present(tmp_path):
    """Safety valve: if a pre-rotation FileHandler exists on the same path,
    we return None rather than silently shadowing it. Caller gets a chance
    to notice."""
    import log_setup
    log_path = tmp_path / "existing.log"
    logger = logging.getLogger("test.attach.existing_plain")
    logger.handlers.clear()
    plain = logging.FileHandler(log_path, encoding="utf-8")
    logger.addHandler(plain)
    try:
        result = log_setup.attach_rotating_handler(logger, log_path)
        assert result is None
    finally:
        logger.handlers.clear()
        plain.close()


# ── preemptive_rotate ────────────────────────────────────────────────────────

def test_preemptive_rotate_no_file_returns_false(tmp_path):
    import log_setup
    assert log_setup.preemptive_rotate(tmp_path / "missing.log") is False


def test_preemptive_rotate_under_threshold_returns_false(tmp_path):
    import log_setup
    log_path = tmp_path / "tiny.log"
    log_path.write_bytes(b"short")
    assert log_setup.preemptive_rotate(log_path, max_bytes=1_000_000) is False
    # File is untouched.
    assert log_path.read_bytes() == b"short"


def test_preemptive_rotate_over_threshold_rotates(tmp_path):
    import log_setup
    log_path = tmp_path / "big.log"
    log_path.write_bytes(b"x" * 500)
    assert log_setup.preemptive_rotate(log_path, max_bytes=100, backup_count=3) is True
    # Original was renamed to .1; new path doesn't exist yet (next append creates it).
    assert not log_path.exists()
    assert (tmp_path / "big.log.1").exists()


def test_preemptive_rotate_shifts_existing_backups(tmp_path):
    """Simulate multiple prior rotations — .1 → .2, .2 → .3 before new log → .1."""
    import log_setup
    (tmp_path / "app.log").write_bytes(b"x" * 500)
    (tmp_path / "app.log.1").write_bytes(b"older")
    (tmp_path / "app.log.2").write_bytes(b"oldest")
    assert log_setup.preemptive_rotate(
        tmp_path / "app.log", max_bytes=100, backup_count=3,
    ) is True

    assert not (tmp_path / "app.log").exists()
    assert (tmp_path / "app.log.1").read_bytes() == b"x" * 500  # was main
    assert (tmp_path / "app.log.2").read_bytes() == b"older"
    assert (tmp_path / "app.log.3").read_bytes() == b"oldest"


def test_preemptive_rotate_drops_oldest_when_at_cap(tmp_path):
    """backup_count=2 means .1 and .2 — when rotating, the old .2 is dropped."""
    import log_setup
    (tmp_path / "app.log").write_bytes(b"x" * 500)
    (tmp_path / "app.log.1").write_bytes(b"younger")
    (tmp_path / "app.log.2").write_bytes(b"oldest-must-drop")
    assert log_setup.preemptive_rotate(
        tmp_path / "app.log", max_bytes=100, backup_count=2,
    ) is True

    assert (tmp_path / "app.log.1").read_bytes() == b"x" * 500
    assert (tmp_path / "app.log.2").read_bytes() == b"younger"
    # With backup_count=2 we only keep .1 and .2; what used to be .2 is gone.


def test_preemptive_rotate_accepts_str_and_path(tmp_path):
    import log_setup
    p = tmp_path / "str.log"
    p.write_bytes(b"x" * 500)
    # Pass str (bat-file style) — must not blow up.
    assert log_setup.preemptive_rotate(str(p), max_bytes=100) is True
    assert (tmp_path / "str.log.1").exists()


def test_preemptive_rotate_boundary_semantics_match_rotating_handler(tmp_path):
    """At size == max_bytes we DO rotate, matching RotatingFileHandler's
    ``stream.tell() >= maxBytes`` behavior. Under (size < max_bytes) we don't.
    One byte below the line keeps the log in place; equal or above rolls."""
    import log_setup
    below = tmp_path / "below.log"
    below.write_bytes(b"x" * 99)
    assert log_setup.preemptive_rotate(below, max_bytes=100) is False
    assert below.exists()

    at_boundary = tmp_path / "at.log"
    at_boundary.write_bytes(b"x" * 100)
    assert log_setup.preemptive_rotate(at_boundary, max_bytes=100) is True
    assert not at_boundary.exists()
    assert (tmp_path / "at.log.1").exists()


# ── engine wire-up: grade_picks + run_picks ──────────────────────────────────

def _strip_comments(source: str) -> str:
    """Remove full-line and trailing `#` comments so regex searches don't hit
    doc-comments that explain code we just removed. Copied from test_section30."""
    out_lines = []
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Trailing comments — primitive but good enough for our grep needs here.
        # (Doesn't handle `#` inside string literals, but we don't have any.)
        idx = line.find("#")
        if idx != -1:
            line = line[:idx]
        out_lines.append(line)
    return "\n".join(out_lines)


def test_grade_picks_no_plain_filehandler_in_executable_source():
    """Executable code in grade_picks.py must not instantiate a plain
    logging.FileHandler for the jonnyparlay log — it must go through
    attach_rotating_handler. Comments are stripped to avoid false positives
    from the migration note."""
    src = _strip_comments((ENGINE_DIR / "grade_picks.py").read_text(encoding="utf-8"))
    assert not re.search(r"\blogging\.FileHandler\b", src), \
        "grade_picks.py still uses logging.FileHandler — should be attach_rotating_handler"


def test_run_picks_no_plain_filehandler_in_executable_source():
    src = _strip_comments((ENGINE_DIR / "run_picks.py").read_text(encoding="utf-8"))
    assert not re.search(r"\blogging\.FileHandler\b", src), \
        "run_picks.py still uses logging.FileHandler — should be attach_rotating_handler"


def test_grade_picks_imports_attach_rotating_handler():
    src = (ENGINE_DIR / "grade_picks.py").read_text(encoding="utf-8")
    assert "attach_rotating_handler" in src


def test_run_picks_imports_attach_rotating_handler():
    src = (ENGINE_DIR / "run_picks.py").read_text(encoding="utf-8")
    assert "attach_rotating_handler" in src


def test_grade_picks_logger_has_rotating_handler(tmp_path, monkeypatch):
    """Integration: importing grade_picks attaches a RotatingFileHandler."""
    # Redirect the log path so we don't scribble on the real file.
    fake_home = tmp_path / "fake_home"
    (fake_home / "Documents" / "JonnyParlay" / "data").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))  # Windows

    # Clear any prior handlers on the shared logger name.
    logging.getLogger("jonnyparlay").handlers.clear()

    # Reload to re-run module-level attach call with the patched HOME.
    if "grade_picks" in sys.modules:
        del sys.modules["grade_picks"]
    # Import of grade_picks pulls a LOT of deps (requests, secrets_config). We
    # only want to test the handler wiring — skip if imports fail on a clean
    # box rather than failing the test.
    try:
        importlib.import_module("grade_picks")
    except Exception as e:
        pytest.skip(f"grade_picks import failed (deps missing in test env): {e}")

    logger = logging.getLogger("jonnyparlay")
    rotating = [h for h in logger.handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)]
    try:
        assert len(rotating) >= 1, \
            "Expected at least one RotatingFileHandler on 'jonnyparlay' logger"
    finally:
        for h in rotating:
            h.close()
        logger.handlers.clear()


# ── start_clv_daemon.bat wiring ──────────────────────────────────────────────

def test_start_clv_daemon_bat_calls_preemptive_rotate():
    """M-24: the bat file must invoke preemptive_rotate BEFORE the python -u
    capture_clv.py line, otherwise Windows can't rename the log while the
    stdout redirect is holding it open."""
    bat = (REPO_ROOT / "start_clv_daemon.bat").read_text(encoding="utf-8")
    assert "preemptive_rotate" in bat

    # Order check: preemptive_rotate line must appear before the first
    # "python -u engine\\capture_clv.py" line.
    rotate_idx = bat.find("preemptive_rotate")
    main_idx = bat.find("python -u engine\\capture_clv.py")
    assert rotate_idx != -1 and main_idx != -1
    assert rotate_idx < main_idx, \
        "preemptive_rotate must be called BEFORE the redirect opens the log"


def test_start_clv_daemon_bat_preserves_s4u_required_env():
    """Audit H-10 / CLAUDE.md: PYTHONUNBUFFERED=1 and python -u are
    non-negotiable for S4U logon. Make sure Section 31's bat edit didn't
    drop them."""
    bat = (REPO_ROOT / "start_clv_daemon.bat").read_text(encoding="utf-8")
    assert "PYTHONUNBUFFERED=1" in bat
    assert "python -u" in bat


def test_start_clv_daemon_bat_preserves_log_appends():
    """Section 31 change should keep the >> "%LOG%" redirect pattern intact."""
    bat = (REPO_ROOT / "start_clv_daemon.bat").read_text(encoding="utf-8")
    assert ">> \"%LOG%\" 2>&1" in bat
    assert "CLV daemon starting" in bat
    assert "CLV daemon exited" in bat


# ── Cross-module sanity ──────────────────────────────────────────────────────

def test_rotation_knobs_used_consistently():
    """No other engine file should redeclare its own rotation size — if it
    does, the contract is drifting. This catches a future copy-paste regression."""
    engine_files = list(ENGINE_DIR.glob("*.py"))
    offenders = []
    for f in engine_files:
        if f.name == "log_setup.py":
            continue
        src = _strip_comments(f.read_text(encoding="utf-8"))
        if "RotatingFileHandler(" in src:
            # Any direct instantiation outside log_setup is a smell.
            offenders.append(f.name)
    assert not offenders, \
        f"RotatingFileHandler must only be instantiated inside log_setup.py. " \
        f"Found direct usage in: {offenders}"
