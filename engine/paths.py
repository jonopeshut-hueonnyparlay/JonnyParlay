"""Centralized path resolution for JonnyParlay.

The audit flagged (M-26) that the codebase mixed two path strategies:

* Most engine files hardcode ``os.path.expanduser("~/Documents/JonnyParlay/...")``
  so they run cleanly on the Windows workstation where the real bets get
  placed.
* ``clv_report.py`` used the portable
  ``Path(__file__).resolve().parent`` approach so it works in both
  Cowork's Linux mount and on Windows without a symlink.

Both work. The drift shows up in two places:

1. In Cowork, ``grade_picks.py`` / ``weekly_recap.py`` / etc. need a
   ``~/Documents/JonnyParlay/data`` → project-data symlink to run at all,
   which is documented as an operational gotcha in CLAUDE.md.
2. Moving the checkout to a non-Documents folder on Windows breaks every
   hardcoded-path file.

This module is the single resolver. Order of precedence:

1. ``$JONNYPARLAY_ROOT`` environment variable — explicit override. This
   is the clean escape hatch for Cowork (point it at the repo root) and
   for any CI/testing that wants an isolated scratch dir.
2. The repo the module lives in, if it looks like a JonnyParlay tree
   (has a ``data/`` subfolder or a ``pick_log_schema.py``). Handles the
   cases ``engine/paths.py`` → one-up and ``root/paths.py`` → current.
3. Fallback: ``~/Documents/JonnyParlay`` — the Windows home.

Callers should import the pre-resolved ``PROJECT_ROOT`` / ``DATA_DIR``
attributes, or :func:`data_path` / :func:`project_path` for one-off
resolution.
"""
from __future__ import annotations

import os
from pathlib import Path

# Module-level constants — resolved at import time so callers can use
# them as literal `Path` objects instead of callables. All other modules
# key off these.
_ENV_ROOT = "JONNYPARLAY_ROOT"


def _looks_like_project(p: Path) -> bool:
    """Heuristic: does ``p`` look like the JonnyParlay checkout root?

    The anchor is the ``data/`` directory — it's the one folder the
    engine guarantees to create and write into. We deliberately do NOT
    anchor on ``pick_log_schema.py`` because that file lives both in
    ``engine/`` (canonical source) and at the repo root (synced mirror),
    which would cause ``engine/`` itself to falsely identify as the root
    and make ``paths.PICK_LOG_PATH`` point at ``engine/data/pick_log.csv``.
    """
    return (p / "data").is_dir()


def _resolve_project_root() -> Path:
    """Return the canonical project root per the docstring precedence."""
    env = os.environ.get(_ENV_ROOT, "").strip()
    if env:
        # Explicit override. Resolve but don't validate existence — a
        # bootstrap script may be pointing at a dir it's about to create.
        return Path(os.path.expanduser(env)).resolve()

    here = Path(__file__).resolve().parent  # engine/ (or project root if synced)
    # Order matters: prefer the parent first so the canonical
    # ``engine/paths.py`` module resolves to the repo root, not to
    # engine/ itself (which would shadow the real data/ directory if one
    # ever gets dropped under engine/ — unlikely, but keeps the resolver
    # honest). For the root-synced mirror, ``here`` has data/ directly
    # and the ``here`` candidate wins on the second check.
    if _looks_like_project(here.parent):
        return here.parent
    if _looks_like_project(here):
        return here

    # Final fallback — the Windows home. Mirrors the historical hardcode.
    return Path(os.path.expanduser("~/Documents/JonnyParlay")).resolve()


PROJECT_ROOT: Path = _resolve_project_root()
DATA_DIR: Path = PROJECT_ROOT / "data"


def project_path(*parts: str) -> Path:
    """Join ``parts`` onto :data:`PROJECT_ROOT`."""
    return PROJECT_ROOT.joinpath(*parts)


def data_path(*parts: str) -> Path:
    """Join ``parts`` onto :data:`DATA_DIR` (``PROJECT_ROOT/data``)."""
    return DATA_DIR.joinpath(*parts)


# Canonical file paths used across the engine. Keeping these in one
# place means a path rename is a one-liner instead of a sweeping sed.
# JONNYPARLAY_PICK_LOG env var overrides the default path — used by
# generate_projections.py --shadow to route custom-projection picks to
# a separate log (pick_log_custom.csv) without touching the live log.
PICK_LOG_PATH: Path = Path(os.environ["JONNYPARLAY_PICK_LOG"]) if "JONNYPARLAY_PICK_LOG" in os.environ else DATA_DIR / "pick_log.csv"
PICK_LOG_MANUAL_PATH: Path = DATA_DIR / "pick_log_manual.csv"
PICK_LOG_MLB_PATH: Path = DATA_DIR / "pick_log_mlb.csv"
DISCORD_GUARD_FILE: Path = DATA_DIR / "discord_posted.json"
LOG_FILE_PATH: Path = DATA_DIR / "jonnyparlay.log"
CLV_DAEMON_LOG: Path = DATA_DIR / "clv_daemon.log"
CLV_DAEMON_LOCK: Path = DATA_DIR / "clv_daemon.lock"


__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "PICK_LOG_PATH",
    "PICK_LOG_MANUAL_PATH",
    "PICK_LOG_MLB_PATH",
    "DISCORD_GUARD_FILE",
    "LOG_FILE_PATH",
    "CLV_DAEMON_LOG",
    "CLV_DAEMON_LOCK",
    "project_path",
    "data_path",
]
