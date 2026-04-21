"""Shared rotating-log wiring for picksbyjonny engine.

Audit M-24 + M-25 (closed Apr 20 2026).

Before this module, two log files grew unbounded:

    data/jonnyparlay.log   — appended by run_picks.py + grade_picks.py
    data/clv_daemon.log    — appended by start_clv_daemon.bat's stdout redirect

Neither had rotation. On a busy week `jonnyparlay.log` grows fast enough that
a year from now it's tens of MB and `tail -f` starts feeling sluggish; the
daemon log is worse because stdout logging on the CLV daemon is verbose.

We fix both with Python's ``RotatingFileHandler`` (for file-based loggers)
and a ``preemptive_rotate`` helper (for files owned by external redirects
like the bat file's ``>>`` operator, which Python can't rename while open).

Public API
----------
- ``ROTATION_MAX_BYTES`` / ``ROTATION_BACKUP_COUNT``: frozen defaults so
  test_section31 can lock the contract and catch silent drift.
- ``attach_rotating_handler(logger, path, *, max_bytes, backup_count)``:
  idempotent handler attachment. Safe to call multiple times per logger.
- ``preemptive_rotate(path, *, max_bytes, backup_count)``: standalone
  rename-based rotation that works on files not currently held by a
  Python logger (i.e. the bat-redirected clv_daemon.log). Called by
  start_clv_daemon.bat BEFORE `python capture_clv.py` opens the redirect.

Why a shared helper (vs. inline in each file):
The cross-module guarantee is what matters — if run_picks and grade_picks
drift to different rotation sizes, log debugging gets weird. One knob, one
source of truth.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

# ── Rotation knobs ────────────────────────────────────────────────────────────
# 5 MB × 5 backups = 25 MB ceiling per log path. At current append rates
# (jonnyparlay.log: ~10 KB/day, clv_daemon.log: ~200 KB/day in season) this is
# months of history before the oldest backup is rotated out. Generous enough
# that Jono can still investigate last-season bugs without spelunking.
ROTATION_MAX_BYTES: int = 5_000_000
ROTATION_BACKUP_COUNT: int = 5

# Formatter the engine's file logger has used since Section 2 — kept identical
# here so a blind swap of FileHandler → RotatingFileHandler doesn't change
# existing log line formatting. Grepping old logs still works.
_DEFAULT_FORMAT = "%(asctime)s  %(levelname)-8s %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _handler_targets_path(handler: logging.Handler, path: str) -> bool:
    """Return True if `handler` is already writing to `path` (resolved).

    Used to keep ``attach_rotating_handler`` idempotent — re-importing
    run_picks or grade_picks in a test should not stack duplicate handlers
    on the module-level logger.
    """
    base = getattr(handler, "baseFilename", None)
    if not base:
        return False
    try:
        return os.path.samefile(base, path)
    except (OSError, FileNotFoundError):
        # samefile fails when either path doesn't exist yet. Fall back to a
        # string compare on resolved absolute paths.
        return os.path.abspath(base) == os.path.abspath(path)


def attach_rotating_handler(
    logger: logging.Logger,
    path: str | os.PathLike[str],
    *,
    max_bytes: int = ROTATION_MAX_BYTES,
    backup_count: int = ROTATION_BACKUP_COUNT,
    fmt: str = _DEFAULT_FORMAT,
    datefmt: str = _DEFAULT_DATEFMT,
    encoding: str = "utf-8",
) -> logging.handlers.RotatingFileHandler | None:
    """Attach a RotatingFileHandler to ``logger`` writing to ``path``.

    Idempotent: if a handler on this logger already targets the same file,
    returns the existing handler instead of stacking a duplicate. This lets
    run_picks.py and grade_picks.py — both of which share the ``jonnyparlay``
    logger name — safely both call this helper without doubling output.

    Returns the handler (new or existing), or None if logger already has a
    non-rotating handler at this path (shouldn't happen in practice, but we
    don't silently drop in case of hand-edits).

    Side effect: creates the parent directory if missing.
    """
    target_path = os.fspath(path)
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)

    # Idempotency check — return existing rotating handler if present.
    for existing in logger.handlers:
        if isinstance(existing, logging.handlers.RotatingFileHandler) \
                and _handler_targets_path(existing, target_path):
            return existing
        # If a plain FileHandler was already attached to the same path
        # (pre-rotation code path), we leave it in place and bail so the
        # caller can notice and fix — silently replacing would hide bugs.
        if isinstance(existing, logging.FileHandler) \
                and not isinstance(existing, logging.handlers.RotatingFileHandler) \
                and _handler_targets_path(existing, target_path):
            return None

    handler = logging.handlers.RotatingFileHandler(
        target_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding=encoding,
    )
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(handler)
    return handler


def preemptive_rotate(
    path: str | os.PathLike[str],
    *,
    max_bytes: int = ROTATION_MAX_BYTES,
    backup_count: int = ROTATION_BACKUP_COUNT,
) -> bool:
    """Rotate ``path`` if it exceeds ``max_bytes``, using rename-based shift.

    Designed for files NOT held by a Python logger — specifically the bat
    file's stdout redirect target ``data/clv_daemon.log``. The bat file
    calls this via ``python -c "..."`` BEFORE launching capture_clv.py, so
    no process is holding an open handle on Windows when the rename happens.

    Rotation scheme matches ``RotatingFileHandler``:
        path.N  → deleted (oldest)
        path.K  → path.K+1   (for K in backup_count-1 .. 1)
        path    → path.1
        path    → new empty file (created on next append)

    Returns True if rotation happened, False if file was under the size
    threshold or didn't exist. Never raises — an I/O error during rotation
    is logged to stderr and swallowed, because failing here would crash the
    daemon launcher for no reason. Losing a rotation cycle is not fatal;
    the log is just a bit bigger.
    """
    p = Path(os.fspath(path))
    if not p.exists():
        return False
    try:
        size = p.stat().st_size
    except OSError:
        return False
    if size < max_bytes:
        return False

    # Shift older backups first: path.(N-1) → path.N, ..., path.1 → path.2
    for i in range(backup_count - 1, 0, -1):
        src = p.with_name(f"{p.name}.{i}")
        dst = p.with_name(f"{p.name}.{i + 1}")
        if src.exists():
            try:
                if dst.exists():
                    dst.unlink()
                src.rename(dst)
            except OSError as e:  # noqa: PERF203 — loop is tiny
                import sys
                print(f"[log_setup] preemptive_rotate: could not shift {src} → {dst}: {e}",
                      file=sys.stderr)
                return False

    # Finally: path → path.1
    final_dst = p.with_name(f"{p.name}.1")
    try:
        if final_dst.exists():
            final_dst.unlink()
        p.rename(final_dst)
    except OSError as e:
        import sys
        print(f"[log_setup] preemptive_rotate: could not rotate {p}: {e}",
              file=sys.stderr)
        return False

    return True


__all__ = [
    "ROTATION_MAX_BYTES",
    "ROTATION_BACKUP_COUNT",
    "attach_rotating_handler",
    "preemptive_rotate",
]
