"""Section 41 — print → logging migration (audit M-28).

Every long-running engine entry point used bare ``print()`` for progress,
warnings, and errors. The audit flagged this as "not urgent" because the
bat-file's ``>> "%LOG%" 2>&1`` redirect already captured the lines — but
without per-line timestamps, level metadata, or the ability to filter to
just warnings during a postmortem.

Section 41 closes M-28 by:

1. Introducing ``engine/engine_logger.py`` — a single configuration point
   that returns a named logger with a stderr stream handler (for live
   daemon watching) and an optional ``RotatingFileHandler`` wired through
   ``log_setup.attach_rotating_handler`` (so warnings + errors persist
   across daemon restarts without blowing up disk).

2. Migrating the *warning / error class* prints in ``engine/capture_clv.py``
   to ``logger.warning`` / ``logger.error`` calls. Progress prints that
   are part of the daemon's interactive UX stay as ``print()`` — Jono
   watches those live during game windows, so routing them through a
   logger with a timestamp prefix would regress the daily workflow.

3. Enforcing the contract with regression tests so a future edit can't
   silently reintroduce a bare ``print("    ⚠ ...")`` warning without
   showing up as a failing test.

Root-mirror byte-identity is required for every file Section 41 touches.
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"

if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


# ── engine_logger module ───────────────────────────────────────────────────

def test_engine_logger_module_exists():
    assert (ENGINE_DIR / "engine_logger.py").is_file(), (
        "engine/engine_logger.py must exist — M-28 requires a single "
        "configuration entry point for the engine's structured logger."
    )


def test_get_logger_exported():
    import engine_logger
    assert hasattr(engine_logger, "get_logger")
    assert "get_logger" in engine_logger.__all__


def test_get_logger_returns_logger_instance():
    from engine_logger import get_logger, reset_for_tests
    reset_for_tests()
    logger = get_logger("test_m28_basic")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_m28_basic"


def test_get_logger_attaches_stream_handler_to_stderr():
    from engine_logger import get_logger, reset_for_tests
    reset_for_tests()
    logger = get_logger("test_m28_stream")
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    assert stream_handlers, "a stream handler must be wired so daemon watchers see warnings"


def test_get_logger_is_idempotent():
    """Re-importing the caller module must not stack handlers."""
    from engine_logger import get_logger, reset_for_tests
    reset_for_tests()
    a = get_logger("test_m28_idempotent")
    before = len(a.handlers)
    b = get_logger("test_m28_idempotent")
    after = len(b.handlers)
    assert a is b
    assert before == after, (
        "get_logger must not stack handlers when called twice with the "
        "same name — otherwise re-imports cause duplicate log output."
    )


def test_get_logger_with_log_path_attaches_rotating_handler(tmp_path):
    from logging.handlers import RotatingFileHandler
    from engine_logger import get_logger, reset_for_tests
    reset_for_tests()
    log_path = tmp_path / "x.log"
    logger = get_logger("test_m28_rotating", log_path=str(log_path))
    rf = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert rf, (
        "when log_path is passed, a RotatingFileHandler must be attached "
        "so warnings persist with rotation (not infinite growth)."
    )


def test_get_logger_writes_warnings_to_stream(capsys):
    from engine_logger import get_logger, reset_for_tests
    reset_for_tests()
    buf = io.StringIO()
    logger = get_logger("test_m28_write", stream=buf)
    logger.warning("test warning body %s", 42)
    output = buf.getvalue()
    assert "WARNING" in output
    assert "test warning body 42" in output
    # Level name and timestamp-ish prefix are part of the contract.
    assert re.search(r"\d{4}-\d{2}-\d{2}", output)


def test_get_logger_does_not_propagate_to_root():
    """Prevents double-emission through ``logging.basicConfig``-installed handlers."""
    from engine_logger import get_logger, reset_for_tests
    reset_for_tests()
    logger = get_logger("test_m28_no_propagate")
    assert logger.propagate is False


def test_reset_for_tests_is_exported():
    import engine_logger
    assert "reset_for_tests" in engine_logger.__all__


# ── capture_clv migration ─────────────────────────────────────────────────

def test_capture_clv_imports_engine_logger():
    src = (ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8")
    assert "from engine_logger import get_logger" in src, (
        "capture_clv.py must route warnings + errors through engine_logger"
    )


def test_capture_clv_has_module_level_logger():
    src = (ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8")
    # Module-level ``logger = get_logger("capture_clv", ...)``.
    assert re.search(r"^\s*logger\s*=\s*get_logger\(", src, re.MULTILINE), (
        "capture_clv.py must define a module-level logger so every warning "
        "site routes through the same named logger."
    )


def test_capture_clv_warnings_routed_through_logger():
    """Writer-side warnings must use logger.warning / logger.error, not print."""
    src = (ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8")
    # At least these known sites should be on the logger now.
    expected_logger_calls = [
        "logger.warning(\"Checkpoint save failed",
        "logger.warning(\"Could not acquire lock on",
        "logger.warning(\"schema sidecar write failed",
        "logger.warning(\"capture_attempts cap hit",
        "logger.warning(\"Odds API quota low",
    ]
    for needle in expected_logger_calls:
        assert needle in src, f"expected logger call missing: {needle!r}"


def test_capture_clv_warning_prints_count_dropped():
    """Warning-class prints should be substantially reduced post-migration.

    Before Section 41: the file had 13+ ``print("    ⚠ ...")`` sites for
    retry + quota + lock warnings. Section 41 migrated the stable, known
    warning sites to logger calls. Allow a small tail of ``⚠`` prints
    that are genuinely user-facing progress (daemon watcher UX), but
    the count must be ≤ 6 to prove the migration happened.
    """
    src = (ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8")
    warn_prints = re.findall(r"^\s*print\(f?\".*?⚠", src, re.MULTILINE)
    assert len(warn_prints) <= 6, (
        f"Too many ``print('⚠ ...')`` calls still in capture_clv.py "
        f"({len(warn_prints)} found). Migrate additional warning sites "
        f"to logger.warning / logger.error per M-28."
    )


def test_capture_clv_error_class_prints_migrated():
    """HTTP error / JSON error / give-up prints should be on the logger."""
    src = (ENGINE_DIR / "capture_clv.py").read_text(encoding="utf-8")
    expected = [
        "logger.error(\"%s: unexpected",
        "logger.error(\"%s: HTTP %d (no retry)",
        "logger.error(\"%s: bad JSON response",
        "logger.error(\"%s: gave up after",
    ]
    for needle in expected:
        assert needle in src, f"expected logger.error call missing: {needle!r}"


# ── Root-mirror contract ───────────────────────────────────────────────────

# L16 (Apr 30 2026): capture_clv.py is a runpy shim; engine_logger.py has no root
# copy. test_tail_guard.py guards shim validity. (H1/H2, May 1 2026)
