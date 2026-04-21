"""Shared Discord post-dedup guard — cross-process safe.

Every Discord-posting writer in the engine (morning_preview, weekly_recap,
grade_picks, run_picks) reads and writes the same guard file:

    ~/Documents/JonnyParlay/data/discord_posted.json

Previously each file had its own _load_guard / _save_guard, each with its
own tmp+replace logic and no cross-process coordination. Two writers firing
at the same second could clobber each other and re-post a @everyone ping.

This module is the single source of truth:

- FileLock at discord_posted.json.lock serializes every reader and writer
- Atomic write: tmp file → flush → fsync → os.replace
- 90-day TTL prune on every save
- If filelock is missing, falls back to best-effort direct write + warning

Public API:
    load_guard()         -> dict
    save_guard(guard)    -> None
    prune_guard(guard)   -> dict
    is_posted(key)       -> bool
    mark_posted(key)     -> None     # atomic read-modify-write
"""

from __future__ import annotations

import json  # noqa: F401 — retained for load path (reader still parses JSON)
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure sibling-module imports (io_utils) resolve whether this file is
# imported as engine.discord_guard or via a `sys.path.insert(0, "engine")`
# shim from the top-level launchers.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from io_utils import atomic_write_json  # noqa: E402

try:
    from filelock import FileLock, Timeout as _FileLockTimeout
except ImportError as e:  # pragma: no cover — enforced as a hard dependency
    raise ImportError(
        "filelock is required for cross-process safe Discord guard I/O. "
        "Install it: pip install filelock --break-system-packages"
    ) from e

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GUARD_FILE: Path = Path(os.path.expanduser("~/Documents/JonnyParlay/data/discord_posted.json"))
LOCK_FILE: str = str(GUARD_FILE) + ".lock"

# ---------------------------------------------------------------------------
# Knobs
# ---------------------------------------------------------------------------

GUARD_TTL_DAYS: int = 90
LOCK_TIMEOUT_S: int = 30

# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def prune_guard(guard: dict) -> dict:
    """Drop guard keys whose embedded YYYY-MM-DD date exceeds the TTL.

    Keys look like 'recap:2026-04-14', 'killshot:2026-04-15:player', etc.
    The first date token (10 chars, positions 4 and 7 = '-') is authoritative.
    Keys without a parseable date are preserved.
    """
    cutoff = (
        datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
        - timedelta(days=GUARD_TTL_DAYS)
    )
    pruned: dict = {}
    for key, val in guard.items():
        keep = True
        for p in key.split(":"):
            if len(p) == 10 and p[4] == "-" and p[7] == "-":
                try:
                    dt = datetime.strptime(p, "%Y-%m-%d")
                    if dt < cutoff:
                        keep = False
                    break  # first date token is authoritative
                except ValueError:
                    continue
        if keep:
            pruned[key] = val
    return pruned


def _load_unlocked() -> dict:
    try:
        with open(GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_unlocked(guard: dict) -> None:
    # Delegated to the shared io_utils.atomic_write_json helper — one
    # fsync policy, one tmp-cleanup branch, across every guard writer.
    atomic_write_json(GUARD_FILE, prune_guard(guard))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_guard() -> dict:
    """Load the guard dict under the shared cross-process lock."""
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            return _load_unlocked()
    except _FileLockTimeout:
        print(
            f"  ⚠ [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on load "
            "— reading without lock (stale-read risk)"
        )
        return _load_unlocked()


def save_guard(guard: dict) -> None:
    """Save the guard dict atomically under the shared cross-process lock."""
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            _save_unlocked(guard)
    except _FileLockTimeout:
        print(
            f"  ⚠ [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on save "
            "— writing without lock (clobber risk)"
        )
        _save_unlocked(guard)


def is_posted(key: str) -> bool:
    """Convenience: has this guard key been marked already?"""
    return bool(load_guard().get(key))


def mark_posted(key: str) -> None:
    """Atomic read-modify-write: set guard[key] = True under one lock.

    Use this instead of a load() / mutate / save() pattern when multiple
    writers might race — this keeps the RMW inside one lock acquisition
    so neither writer clobbers the other's key.
    """
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            g = _load_unlocked()
            g[key] = True
            _save_unlocked(g)
    except _FileLockTimeout:
        print(
            f"  ⚠ [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on "
            f"mark_posted({key!r}) — writing without lock (clobber risk)"
        )
        g = _load_unlocked()
        g[key] = True
        _save_unlocked(g)


def claim_post(key: str) -> bool:
    """Atomic test-and-set. Returns True if THIS process just claimed `key`,
    False if another process already claimed it.

    This is the correct primitive to stop duplicate Discord posts when two
    processes race (Task Scheduler retry + a manual run, two manual runs,
    etc.). Call this BEFORE the webhook POST. If it returns False, bail.
    If it returns True and the webhook then fails, call release_post(key)
    so a subsequent retry can re-claim.

    Preserves the 'check' and 'set' inside one FileLock acquisition —
    the mark_posted / is_posted pair does NOT (load / mutate / save has
    a TOCTOU window).
    """
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            g = _load_unlocked()
            if g.get(key):
                return False
            g[key] = True
            _save_unlocked(g)
            return True
    except _FileLockTimeout:
        # Fall back: best-effort test-and-set without a lock. Risk is a
        # duplicate post, but that's strictly better than blocking forever.
        print(
            f"  ⚠ [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on "
            f"claim_post({key!r}) — falling back to unlocked claim (duplicate-post risk)"
        )
        g = _load_unlocked()
        if g.get(key):
            return False
        g[key] = True
        _save_unlocked(g)
        return True


def release_post(key: str) -> None:
    """Un-claim a key. Use after a FAILED webhook post so the next run can
    re-claim and retry. No-op if the key isn't set.

    DO NOT call this after a successful post — the whole point of the claim
    is that it survives across runs so no one re-posts.
    """
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            g = _load_unlocked()
            if key in g:
                del g[key]
                _save_unlocked(g)
    except _FileLockTimeout:
        print(
            f"  ⚠ [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on "
            f"release_post({key!r}) — releasing without lock (clobber risk)"
        )
        g = _load_unlocked()
        if key in g:
            del g[key]
            _save_unlocked(g)
