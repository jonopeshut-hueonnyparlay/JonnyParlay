"""engine_logger.py — shared structured-logging helper for the engine.

Audit M-28 (print → logging). Every long-running engine entry point
(run_picks, grade_picks, capture_clv, weekly_recap, morning_preview, …)
historically used bare ``print()`` for everything — progress, warnings,
errors. The bat-file stdout redirect scooped it all into a flat log with
no levels, no per-line timestamps, and no way to ask "show me just the
warnings from last week".

This helper doesn't rip out every print overnight — M-28 calls the
migration "not urgent" and the daemon's interactive terminal output is
part of Jono's normal run-of-day workflow. What it does:

  1. Give every engine module one entry point — ``get_logger(name)`` —
     for warning / error / structured-info emission.
  2. Wire a stderr ``StreamHandler`` (so warnings still show up on the
     live terminal for a daemon watcher) AND — when a ``log_path`` is
     provided — a ``RotatingFileHandler`` using the shared size/backup
     knobs from ``log_setup.py``.
  3. Stay idempotent: calling ``get_logger`` twice with the same name
     does not stack handlers. That's important for test harnesses and
     for modules re-imported across different CLI entry points.

Usage::

    from engine_logger import get_logger
    logger = get_logger(__name__, log_path=str(DATA_DIR / "clv_daemon.log"))
    logger.warning("Quota low: %s requests remaining", remaining)
    logger.error("Webhook POST failed: %s", exc)

Callers that want the old inline print for a progress line can still
use ``print()``; the engine doesn't force a full migration. But any
``⚠`` / ``ERROR`` style message should route through this logger so
downstream log analysis (grep by level, timestamp windowing) works.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from log_setup import attach_rotating_handler


# Formatter shared across every engine logger. Keeping it identical to
# log_setup._DEFAULT_FORMAT means `tail -f` on the rotating file log looks
# the same whether the source was an engine module or a plain-print bat
# redirect that happened to end up in the file. Stable format = stable
# grep patterns.
_FORMAT = "%(asctime)s  %(levelname)-8s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


# Track which names have been fully configured so a second call is a no-op.
# Keyed by (logger_name, log_path) so switching destinations in tests works.
_CONFIGURED: set[tuple[str, str]] = set()


def _has_stream_handler_to(logger: logging.Logger, stream) -> bool:
    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is stream:
            return True
    return False


def get_logger(
    name: str,
    log_path: Optional[str | os.PathLike[str]] = None,
    *,
    level: int = logging.INFO,
    stream=None,
) -> logging.Logger:
    """Return an engine-configured logger.

    Parameters
    ----------
    name
        Module-qualified logger name — pass ``__name__`` from the caller.
    log_path
        If provided, a ``RotatingFileHandler`` (via
        ``log_setup.attach_rotating_handler``) is attached so warnings and
        errors land in a persisted, rotated log file. Pass ``None`` if the
        caller only wants console logging.
    level
        Effective logger level. Defaults to INFO — warnings + errors +
        explicit infos show up, debug spam is filtered out.
    stream
        Override the stderr stream. Primarily exists so tests can inject
        an ``io.StringIO`` and assert on the output without monkeypatching
        ``sys.stderr`` globally.

    Guarantees
    ----------
    * Calling twice with the same name + log_path does not stack handlers.
    * The stream handler writes to ``sys.stderr`` by default — warnings
      stay visible in the daemon's terminal even when stdout is piped
      elsewhere.
    * ``logger.propagate`` is left False so this logger's output does not
      double-emit through the root logger's handlers (which may or may
      not exist depending on whether some upstream code called
      ``logging.basicConfig``).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    effective_stream = stream if stream is not None else sys.stderr
    log_path_str = str(log_path) if log_path is not None else ""
    key = (name, log_path_str)

    if key in _CONFIGURED:
        return logger

    if not _has_stream_handler_to(logger, effective_stream):
        sh = logging.StreamHandler(effective_stream)
        sh.setLevel(level)
        sh.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        logger.addHandler(sh)

    if log_path is not None:
        # attach_rotating_handler is idempotent on its own (Section 31
        # enforced this via tests), so double-calling is safe.
        attach_rotating_handler(logger, str(log_path))

    _CONFIGURED.add(key)
    return logger


def reset_for_tests() -> None:
    """Clear the idempotency cache.

    Production callers should never touch this. Used by the regression
    suite when a test wants to re-exercise the "first call configures
    handlers" branch with a fresh logger state.
    """
    _CONFIGURED.clear()


__all__ = ["get_logger", "reset_for_tests"]
