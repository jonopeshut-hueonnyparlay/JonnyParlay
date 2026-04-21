"""Shared low-level I/O helpers.

Architectural audit note #2 (closed Apr 21 2026): five modules re-implemented
the same "write JSON atomically" dance — tempfile.mkstemp → json.dump → flush →
fsync → os.replace, with a tmp-cleanup except branch. The five copies drifted
in subtle ways (some used ``CHECKPOINT.with_suffix(".tmp")`` instead of
mkstemp, one forgot fsync, one had a different error branch). Consolidating
into one helper means fsync is fixed once, and any future change (e.g. Windows
long-path handling) happens in a single place.

Public API
----------
:func:`atomic_write_json`  — the one entry point. Takes a path + a
JSON-serialisable object, writes atomically, raises on failure.

Semantics
---------
* Parent directory is created if missing.
* The tmp file is created in the **same directory** as the target — required
  for ``os.replace`` to be atomic on both POSIX and Windows (cross-device
  renames silently fall back to copy+delete, which is not atomic).
* Tmp file naming: ``<basename>.<random>.tmp``. Matches the existing
  ``mkstemp(prefix=basename + ".", suffix=".tmp")`` convention every caller
  was already using, so the ``preflight.bat`` stale-tmp cleanup keeps
  catching these.
* On success: ``os.replace(tmp, path)`` — atomic rename, no partial-write
  window.
* On failure: the tmp file is unlinked (best-effort) and the exception is
  re-raised. Callers that want a best-effort fallback to a plain overwrite
  wrap this helper themselves — we don't silently swallow here because
  callers in different modules have different policies (guard-file savers
  have a fallback; the CLV checkpoint does not).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(
    path: str | os.PathLike[str],
    data: Any,
    *,
    indent: int | None = 2,
    encoding: str = "utf-8",
) -> None:
    """Write ``data`` as JSON to ``path`` atomically.

    The write goes to a sibling tmp file, is fsynced, and then atomically
    renamed into place. A crash mid-write leaves either the old file
    unchanged or the new file complete — never a truncated-to-empty file.

    Parameters
    ----------
    path:
        Target path. Created if missing (including parent directory).
    data:
        Any object that ``json.dumps`` accepts.
    indent:
        Passed through to ``json.dump``. Default ``2`` matches every existing
        caller (guard files + CLV checkpoint all use indent=2).
    encoding:
        File encoding. Default ``utf-8``.

    Raises
    ------
    Any exception from the write (``OSError``, ``TypeError`` on non-JSON
    data, etc.) is re-raised after the tmp file is cleaned up. Callers
    decide whether to catch and fall back.
    """
    target = Path(os.fspath(path))
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            json.dump(data, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
    except Exception:
        # Best-effort cleanup of the orphaned tmp file. We swallow OSError
        # here because a failed unlink is strictly less important than
        # reporting the original write failure — and preflight.bat sweeps
        # any stray ``*.tmp`` on the next run.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


__all__ = ["atomic_write_json"]
