"""pick_log_io.py — canonical locked readers/writers for pick_log CSVs.

Audit H-8 / M-series, closed Apr 20 2026.

Every reader of pick_log.csv (and its sibling logs — pick_log_manual.csv,
pick_log_mlb.csv) MUST acquire the same FileLock the writers use, otherwise
a reader can race a capture_clv.py / grade_picks.py / run_picks.py write and
see a partial/stale row set.

Public surface:
  - read_rows_locked(log_path, lock_timeout=30)       -> (rows, fieldnames)
  - read_rows_locked_if_exists(log_path, ...)         -> same, or ([], [])
  - pick_log_lock(log_path, lock_timeout=30)          -> context manager

`pick_log_lock` is for compound read-modify-write sequences that want to
hold the lock across both the read and the subsequent atomic write.
"""

from __future__ import annotations

import csv
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Optional

try:
    from filelock import FileLock, Timeout as FileLockTimeout
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "filelock is required (audit C-1). Install: "
        "pip install filelock --break-system-packages"
    ) from e

# Canonical pick_log schema (audit H-3). Migration is applied on read by default
# so every caller sees a canonical-shaped row regardless of whether the file was
# written under an older schema version.
from pick_log_schema import (
    CANONICAL_HEADER,
    SCHEMA_VERSION,
    detect_schema_version,
    migrate_row,
    read_schema_sidecar,
    validate_header,
)


class SchemaVersionMismatchError(RuntimeError):
    """Raised when a pick_log sidecar declares a schema version newer than
    this build of the engine knows how to read.

    Arch note #5: silently migrating a future-version row would hide new
    columns or — worse — misinterpret renamed columns. Fail fast so the
    operator upgrades the engine (or deletes/rolls-back the sidecar) before
    any reader touches rows it can't faithfully represent.
    """


__all__ = [
    "read_rows_locked",
    "read_rows_locked_if_exists",
    "load_rows",
    "pick_log_lock",
    "FileLockTimeout",
    "SchemaVersionMismatchError",
]

# Track which log paths we've already warned about for legacy-schema drift so
# we don't spam stderr on every invocation of a long-running process.
_schema_warned: set[str] = set()


def _lock_path_for(log_path: str | os.PathLike) -> str:
    """Match the convention used by capture_clv.py and grade_picks.py."""
    return str(log_path) + ".lock"


def _warn(msg: str) -> None:
    # Single-line stderr print so every caller sees the fall-through without
    # pulling in a logger dep. Callers that want structured logging should
    # wrap this helper with their own timeout-catching layer.
    print(msg, file=sys.stderr, flush=True)


def _maybe_migrate(
    rows: list[dict],
    fieldnames: list[str],
    log_path_s: str,
    migrate: bool,
) -> tuple[list[dict], list[str]]:
    """Apply schema migration + emit a one-time warning for legacy logs.

    When ``migrate=True`` (default), every row is passed through
    ``migrate_row`` so callers see canonical-shaped dicts regardless of the
    on-disk schema version. Returns the fieldnames argument unchanged — it
    describes what was ON DISK, not what the rows look like now — so callers
    that care about drift detection can still inspect it.
    """
    if not migrate:
        return rows, fieldnames
    if not fieldnames:
        return rows, fieldnames
    missing, unknown = validate_header(fieldnames)
    if (missing or unknown) and log_path_s not in _schema_warned:
        _schema_warned.add(log_path_s)
        version = detect_schema_version(fieldnames)
        _warn(
            f"[pick_log_io] {log_path_s}: on-disk schema v{version} differs from "
            f"canonical. missing={missing or '[]'} unknown={unknown or '[]'} — "
            f"rows will be migrated to canonical shape on read."
        )
    migrated = [migrate_row(r, source_header=fieldnames) for r in rows]
    return migrated, fieldnames


def _check_sidecar_version(log_path_s: str) -> None:
    """Fail-fast guard against forward-incompatible schema drift.

    Arch note #5: every writer now refreshes a ``<log>.schema.json`` sidecar
    recording the SCHEMA_VERSION it wrote under. If that version is newer
    than what this build knows, raise immediately — silently migrating
    unknown columns would either drop data or misinterpret renamed ones.

    A missing sidecar is tolerated (legacy logs written before the arch-note
    landed).  A corrupt / unparseable sidecar is tolerated (``read_schema_sidecar``
    returns ``None`` for JSON errors).  Only a declared version strictly
    greater than ours is a hard failure.
    """
    sidecar = read_schema_sidecar(log_path_s)
    if not sidecar:
        return
    declared = sidecar.get("schema_version")
    if not isinstance(declared, int):
        return
    if declared > SCHEMA_VERSION:
        raise SchemaVersionMismatchError(
            f"{log_path_s}: sidecar declares schema_version={declared}, but "
            f"this build only understands v{SCHEMA_VERSION}. Upgrade the "
            f"engine (or delete the sidecar if the log was rolled back) "
            f"before reading."
        )


def read_rows_locked(
    log_path: str | os.PathLike,
    lock_timeout: float = 30,
    *,
    migrate: bool = True,
):
    """Read a pick_log CSV under the shared FileLock.

    Returns ``(rows, fieldnames)``. If ``migrate`` is True (default), rows are
    normalized to the canonical schema — missing columns are filled with ``""``
    and unknown columns are dropped. ``fieldnames`` still reflects the on-disk
    header so callers can detect schema drift.

    If the lock can't be acquired within ``lock_timeout`` seconds, logs a loud
    warning and reads anyway (better a possibly-stale read than a hard failure
    that silently breaks reporting).

    Raises ``SchemaVersionMismatchError`` if the sidecar declares a version
    newer than the engine knows (arch note #5).
    """
    log_path_s = str(log_path)
    lock_path = _lock_path_for(log_path_s)

    # Arch note #5: check the sidecar *before* reading so we never hand a
    # caller rows whose shape we can't faithfully represent.
    _check_sidecar_version(log_path_s)

    def _do_read():
        with open(log_path_s, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
        return rows, fieldnames

    try:
        with FileLock(lock_path, timeout=lock_timeout):
            rows, fieldnames = _do_read()
    except FileLockTimeout:
        _warn(
            f"[pick_log_io] Could not acquire read lock on {lock_path} within "
            f"{lock_timeout}s — reading anyway (RISK OF STALE/PARTIAL DATA)"
        )
        rows, fieldnames = _do_read()
    return _maybe_migrate(rows, fieldnames, log_path_s, migrate)


def read_rows_locked_if_exists(
    log_path: str | os.PathLike,
    lock_timeout: float = 30,
    *,
    migrate: bool = True,
):
    """Same as read_rows_locked, but tolerates a missing / empty file.

    Returns ``([], [])`` if the file is missing or zero bytes — matches the
    common caller pattern of ``if log_path.exists() and log_path.stat().st_size > 0``.
    """
    p = Path(log_path)
    if not p.exists():
        return [], []
    try:
        if p.stat().st_size == 0:
            return [], []
    except OSError:
        return [], []
    return read_rows_locked(p, lock_timeout=lock_timeout, migrate=migrate)


# ── Unified loader (audit arch note #3) ──────────────────────────────────────
# Before: analyze_picks, clv_report, morning_preview, weekly_recap, and
# results_graphic each had their own "open + lock + iterate + filter" loop with
# subtly different filter code. One typo'd .upper() or forgotten guard would
# skew downstream P&L / CLV / Discord output. ``load_rows`` centralises the
# shared core so every caller now goes through a single audited code path.

def _as_upper_set(values: Optional[Iterable[str]]) -> Optional[set[str]]:
    if values is None:
        return None
    return {str(v).upper() for v in values}


def _as_str_set(values: Optional[Iterable[Optional[str]]]) -> Optional[set[str]]:
    if values is None:
        return None
    # Normalize None → "" so a row with run_type defaulted to "" still matches
    # callers that include None in their set for defensive back-compat.
    return {"" if v is None else str(v) for v in values}


def load_rows(
    paths: Iterable[str | os.PathLike],
    *,
    run_types: Optional[Iterable[Optional[str]]] = None,
    exclude_run_types: Optional[Iterable[str]] = None,
    sports: Optional[Iterable[str]] = None,
    exclude_sports: Optional[Iterable[str]] = None,
    stats: Optional[Iterable[str]] = None,
    exclude_stats: Optional[Iterable[str]] = None,
    tiers: Optional[Iterable[str]] = None,
    date_equals: Optional[str] = None,
    since: Optional[str] = None,
    date_range: Optional[tuple[Optional[str], Optional[str]]] = None,
    graded_only: bool = False,
    lock_timeout: float = 30,
    migrate: bool = True,
) -> list[dict]:
    """Read + filter pick_log rows from one or more CSV paths under the shared lock.

    Every filter is optional and uses AND semantics — a row must pass *all*
    supplied filters to be returned. Missing or zero-byte paths are silently
    skipped (matches the legacy per-caller patterns).

    Parameters
    ----------
    paths
        Iterable of pick_log CSV paths. Each is read via
        ``read_rows_locked_if_exists`` so the reader lock + schema migration
        apply uniformly.
    run_types, exclude_run_types
        String sets compared against ``row["run_type"]`` (case-sensitive —
        matches the on-disk enum).
    sports, exclude_sports, stats, exclude_stats, tiers
        String sets compared *case-insensitively* against the respective
        row fields — matches every legacy caller's ``.upper()`` comparison.
    date_equals, since, date_range
        Date-string filters (``YYYY-MM-DD``).  Lexicographic comparison is
        correct for ISO dates.  ``date_range=(lo, hi)`` is inclusive on
        both ends; pass ``None`` for either bound to leave it open.
    graded_only
        If True, keep only rows whose result is ``W``/``L``/``P``
        (case-insensitive, whitespace trimmed).
    lock_timeout, migrate
        Forwarded to ``read_rows_locked_if_exists``.
    """
    run_types_set          = _as_str_set(run_types)
    exclude_run_types_set  = _as_str_set(exclude_run_types)
    sports_set             = _as_upper_set(sports)
    exclude_sports_set     = _as_upper_set(exclude_sports)
    stats_set              = _as_upper_set(stats)
    exclude_stats_set      = _as_upper_set(exclude_stats)
    tiers_set              = _as_upper_set(tiers)

    if date_range is not None:
        lo, hi = date_range
    else:
        lo = hi = None

    graded = {"W", "L", "P"}
    out: list[dict] = []

    for p in paths:
        p_path = Path(p)
        if not p_path.exists():
            continue
        try:
            if p_path.stat().st_size == 0:
                continue
        except OSError:
            continue
        rows, _fieldnames = read_rows_locked_if_exists(
            p_path, lock_timeout=lock_timeout, migrate=migrate
        )
        for row in rows:
            rt = row.get("run_type", "") or ""
            if run_types_set is not None and rt not in run_types_set:
                continue
            if exclude_run_types_set is not None and rt in exclude_run_types_set:
                continue

            sp = (row.get("sport") or "").upper()
            if sports_set is not None and sp not in sports_set:
                continue
            if exclude_sports_set is not None and sp in exclude_sports_set:
                continue

            st = (row.get("stat") or "").upper()
            if stats_set is not None and st not in stats_set:
                continue
            if exclude_stats_set is not None and st in exclude_stats_set:
                continue

            tr = (row.get("tier") or "").upper()
            if tiers_set is not None and tr not in tiers_set:
                continue

            date = row.get("date") or ""
            if date_equals is not None and date != date_equals:
                continue
            if since is not None and date < since:
                continue
            if lo is not None and date < lo:
                continue
            if hi is not None and date > hi:
                continue

            if graded_only:
                res = (row.get("result") or "").strip().upper()
                if res not in graded:
                    continue

            out.append(row)
    return out


@contextmanager
def pick_log_lock(log_path: str | os.PathLike, lock_timeout: float = 30) -> Iterator[None]:
    """Context manager version for compound read-modify-write sequences.

    Example::

        with pick_log_lock(PICK_LOG_PATH):
            # read current rows, mutate, write back atomically
            ...

    Falls through (yields) with a loud warning on lock timeout — callers that
    can't tolerate a stale view should check the warning log and abort on
    their own.
    """
    lock_path = _lock_path_for(log_path)
    try:
        with FileLock(lock_path, timeout=lock_timeout):
            yield
    except FileLockTimeout:
        _warn(
            f"[pick_log_io] Could not acquire lock on {lock_path} within "
            f"{lock_timeout}s — proceeding unlocked (RISK OF CORRUPTION)"
        )
        yield


if __name__ == "__main__":  # pragma: no cover
    # Quick smoke test: read data/pick_log.csv if present
    repo = Path(__file__).resolve().parents[1]
    target = repo / "data" / "pick_log.csv"
    if not target.exists():
        print(f"No {target} to read.")
        sys.exit(0)
    rows, fn = read_rows_locked(target, lock_timeout=2)
    print(f"Read {len(rows)} rows, {len(fn)} columns.")
