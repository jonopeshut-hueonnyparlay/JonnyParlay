#!/usr/bin/env python3
"""Tail-truncation guard for core engine files.

This test exists because the Claude Code Write tool has, on multiple
occasions, silently truncated large engine files mid-write when
rewriting them through the Cowork FUSE mount. The truncations were
invisible (no error, no warning) and only surfaced when:

  - pytest collection failed with ``unterminated triple-quoted string``,
  - or ``git diff`` revealed ``\\ No newline at end of file`` at a spot
    that had no business losing its newline,
  - or a runtime symbol vanished ("module has no attribute main").

Every file listed in ``CRITICAL_FILES`` terminates with the standard
``if __name__ == "__main__": main()`` block in its ``engine/`` source.

L16 (Apr 30 2026): root entry-point files are now 5-line runpy shims —
they delegate to engine/ via ``runpy.run_module()`` and intentionally do
NOT contain the canonical tail or the 1000-byte minimum.  The old
hash-equality assertion (engine/ == root) has been removed because shims
and engine source are different by design.

H2 fix (May 1 2026): split engine-copy checks and root-shim checks into
separate parametrized tests so both are verified against their own
correct contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent   # repo root (tests/ is one level down)
ENGINE = HERE / "engine"

# Files that MUST end in the canonical ``if __name__ == "__main__": main()``
# block in the engine/ source and must be >= MIN_BYTES.
CRITICAL_FILES = [
    "run_picks.py",
    "grade_picks.py",
    "analyze_picks.py",
    "morning_preview.py",
    "weekly_recap.py",
]

CANONICAL_TAIL = 'if __name__ == "__main__":\n    main()\n'

# Minimum reasonable size for an engine/ source file.
# run_picks.py is ~5k lines (~200 KB); sub-1 KB means truncation.
MIN_BYTES = 1_000

# Maximum line count for a valid root shim (5-line shims + blank lines).
SHIM_MAX_LINES = 20
SHIM_MARKER    = "runpy.run_module"


# ---------------------------------------------------------------------------
# engine/ copy checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_engine_tail_is_canonical_entrypoint(filename):
    """engine/ source must end with the standard main-guard block."""
    path = ENGINE / filename
    assert path.exists(), f"Missing engine file: {path}"
    text = path.read_text(encoding="utf-8")
    assert text.endswith(CANONICAL_TAIL), (
        f"{path} does not end with the canonical entrypoint.\n"
        f"Last 120 chars:\n{text[-120:]!r}\n"
        f"Expected tail:\n{CANONICAL_TAIL!r}"
    )


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_engine_file_ends_with_newline(filename):
    """engine/ source must end with a newline."""
    path = ENGINE / filename
    assert path.exists(), f"Missing engine file: {path}"
    data = path.read_bytes()
    assert data.endswith(b"\n"), (
        f"{path} does not end with a newline — likely truncated. "
        f"Last 40 bytes: {data[-40:]!r}"
    )


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_engine_file_is_not_suspiciously_small(filename):
    """engine/ source must be at least MIN_BYTES bytes."""
    path = ENGINE / filename
    assert path.exists(), f"Missing engine file: {path}"
    size = path.stat().st_size
    assert size >= MIN_BYTES, (
        f"{path} is only {size} bytes. "
        f"Minimum expected is {MIN_BYTES}. Truncation suspected."
    )


# ---------------------------------------------------------------------------
# root shim checks (L16 architecture)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_root_shim_exists(filename):
    """Root entry-point shim must exist alongside engine/ source."""
    path = HERE / filename
    assert path.exists(), f"Missing root shim: {path}"


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_root_shim_is_short(filename):
    """Root shim must be <= SHIM_MAX_LINES lines (it's a 5-line delegate,
    not a full engine copy)."""
    path = HERE / filename
    assert path.exists(), f"Missing root shim: {path}"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= SHIM_MAX_LINES, (
        f"{path} has {len(lines)} lines — too long to be a shim. "
        f"If the $syncPairs loop in go.ps1 ran, it overwrote the shim "
        f"with the full engine source. Run git checkout {filename} to restore."
    )


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_root_shim_delegates_via_runpy(filename):
    """Root shim must contain the runpy.run_module delegation marker."""
    path = HERE / filename
    assert path.exists(), f"Missing root shim: {path}"
    text = path.read_text(encoding="utf-8")
    assert SHIM_MARKER in text, (
        f"{path} does not contain '{SHIM_MARKER}'. "
        f"It may have been overwritten with the full engine source. "
        f"Run git checkout {filename} to restore the shim."
    )


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_root_shim_delegates_to_correct_module(filename):
    """Root shim must delegate to the matching engine module name."""
    path = HERE / filename
    assert path.exists(), f"Missing root shim: {path}"
    text = path.read_text(encoding="utf-8")
    module_name = filename.replace(".py", "")
    assert f'"{module_name}"' in text or f"'{module_name}'" in text, (
        f"{path} shim does not reference module '{module_name}'. "
        f"It should contain: runpy.run_module(\"{module_name}\", ...)"
    )
