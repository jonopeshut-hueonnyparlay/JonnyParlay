"""Shared Discord post-dedup guard — cross-process safe.

Every Discord-posting writer in the engine (morning_preview, weekly_recap,
grade_picks, run_picks) reads and writes the same guard file:

    ~/Documents/JonnyParlay/data/discord_posted.json

This module is the single source of truth:

- FileLock at discord_posted.json.lock serializes every reader and writer
- Atomic write: tmp file -> flush -> fsync -> os.replace
- 90-day TTL prune on every save
- On JSONDecodeError: regex-rebuild from raw bytes recovers guard keys
  instead of returning {} and re-posting the full card with @everyone.

Public API:
    load_guard()         -> dict
    save_guard(guard)    -> None
    prune_guard(guard)   -> dict
    is_posted(key)       -> bool
    mark_posted(key)     -> None     # atomic read-modify-write
    claim_post(key)      -> bool     # atomic test-and-set (preferred)
    release_post(key)    -> None     # un-claim on webhook failure
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from io_utils import atomic_write_json  # noqa: E402
from paths import DISCORD_GUARD_FILE as _GUARD_FILE_P  # noqa: E402

try:
    from filelock import FileLock, Timeout as _FileLockTimeout
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "filelock is required for cross-process safe Discord guard I/O. "
        "Install it: pip install filelock --break-system-packages"
    ) from e

# ---------------------------------------------------------------------------
# Paths  (M9: resolved via paths.py — honours $JONNYPARLAY_ROOT)
# ---------------------------------------------------------------------------

GUARD_FILE: Path = _GUARD_FILE_P
LOCK_FILE: str = str(GUARD_FILE) + ".lock"

# ---------------------------------------------------------------------------
# Knobs
# ---------------------------------------------------------------------------

GUARD_TTL_DAYS: int = 90
LOCK_TIMEOUT_S: int = 30

# ---------------------------------------------------------------------------
# Regex for corruption recovery (C2 / audit F3.2)
# ---------------------------------------------------------------------------

# Matches: "some:guard:key": true   (case-insensitive for true/True)
# Broad char class -- keys contain colons, spaces, dots, slashes.
_GUARD_KEY_RE = re.compile(
    rb'"((?:[^"\\]|\\.)+?)"\s*:\s*true',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def prune_guard(guard: dict) -> dict:
    """Drop guard keys whose embedded YYYY-MM-DD date exceeds the TTL."""
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
                    break
                except ValueError:
                    continue
        if keep:
            pruned[key] = val
    return pruned


def _rebuild_from_raw_bytes(raw: bytes) -> dict:
    """Emergency key-recovery from a corrupted guard file.

    Scans raw bytes for the pattern '"key": true' and rebuilds the guard dict
    without requiring valid JSON structure.  Only recovers keys mapped to true
    (the only value this module writes) so there is no risk of importing stale
    false entries.  An over-empty result is safer than over-full -- the worst
    case of missing a key is a single re-post, not a spam barrage with @everyone.

    Key format examples (F3.15):
        recap:2026-04-14
        premium_card:2026-04-14
        killshot:2026-04-15:Anthony Edwards:PTS:OVER:27.5
        sgp:2026-04-15:MIN vs DEN
        daily_lay:2026-04-28
    """
    recovered: dict = {}
    for m in _GUARD_KEY_RE.finditer(raw):
        try:
            key = m.group(1).decode("utf-8", errors="replace")
            recovered[key] = True
        except Exception:
            continue
    return recovered


def _load_unlocked() -> dict:
    """Load the guard file, with corruption-recovery fallback.

    Clean read      -> returns parsed JSON dict.
    FileNotFoundError -> returns {} (first run or guard intentionally deleted).
    JSONDecodeError -> attempts to recover existing keys from raw bytes via
      regex scan, logs a warning, and returns whatever was recovered.
      Returning {} on corruption would reset every guard key and cause
      run_picks to repost the full daily card with @everyone (audit C2).
    """
    try:
        with open(GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # File exists but is corrupted -- attempt raw-byte recovery.
        try:
            raw = GUARD_FILE.read_bytes()
        except OSError:
            print(
                "  [discord_guard] CORRUPT guard file AND failed to read "
                "raw bytes -- returning {} (re-post risk). Restore from backup.",
                file=sys.stderr,
            )
            return {}
        recovered = _rebuild_from_raw_bytes(raw)
        preview = list(recovered)[:10]
        ellipsis = "..." if len(recovered) > 10 else ""
        print(
            f"  [discord_guard] guard file is corrupt (JSONDecodeError). "
            f"Recovered {len(recovered)} key(s) from raw bytes via regex scan. "
            f"Keys: {preview}{ellipsis}. "
            "Backup the file and investigate.",
            file=sys.stderr,
        )
        return recovered


def _save_unlocked(guard: dict) -> None:
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
            f"  [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on load "
            "-- reading without lock (stale-read risk)"
        )
        return _load_unlocked()


def save_guard(guard: dict) -> None:
    """Save the guard dict atomically under the shared cross-process lock."""
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            _save_unlocked(guard)
    except _FileLockTimeout:
        print(
            f"  [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on save "
            "-- writing without lock (clobber risk)"
        )
        _save_unlocked(guard)


def is_posted(key: str) -> bool:
    """Convenience: has this guard key been marked already?"""
    return bool(load_guard().get(key))


def mark_posted(key: str) -> None:
    """Atomic read-modify-write: set guard[key] = True under one lock."""
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            g = _load_unlocked()
            g[key] = True
            _save_unlocked(g)
    except _FileLockTimeout:
        print(
            f"  [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on "
            f"mark_posted({key!r}) -- writing without lock (clobber risk)"
        )
        g = _load_unlocked()
        g[key] = True
        _save_unlocked(g)


def claim_post(key: str) -> bool:
    """Atomic test-and-set. Returns True if THIS process just claimed `key`,
    False if another process already claimed it.

    Call this BEFORE the webhook POST. If False, bail. If True and the webhook
    fails, call release_post(key) so a subsequent retry can re-claim.
    Performs check+set inside one FileLock -- mark_posted/is_posted do NOT
    (that pair has a TOCTOU window).
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
        print(
            f"  [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on "
            f"claim_post({key!r}) -- falling back to unlocked claim (duplicate-post risk)"
        )
        g = _load_unlocked()
        if g.get(key):
            return False
        g[key] = True
        _save_unlocked(g)
        return True


def release_post(key: str) -> None:
    """Un-claim a key after a FAILED webhook post so the next run can retry.
    No-op if the key is not set. Do NOT call after a successful post.
    """
    try:
        with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT_S):
            g = _load_unlocked()
            if key in g:
                del g[key]
                _save_unlocked(g)
    except _FileLockTimeout:
        print(
            f"  [discord_guard] lock timeout after {LOCK_TIMEOUT_S}s on "
            f"release_post({key!r}) -- releasing without lock (clobber risk)"
        )
        g = _load_unlocked()
        if key in g:
            del g[key]
            _save_unlocked(g)
