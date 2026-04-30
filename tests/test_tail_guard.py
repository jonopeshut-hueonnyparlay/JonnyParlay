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
``if __name__ == "__main__": main()`` block. If a future tool clobber
lops off the tail, this test fails LOUDLY in CI / pre-commit instead
of shipping a half-written engine.

The test also verifies:

  - Trailing newline (defends against the "no newline at end of file"
    pattern that bit run_picks.py mid-session on 2026-04-21),
  - ``engine/`` vs. repo-root sync — CLAUDE.md mandates that after any
    edit to ``engine/run_picks.py`` (or grade/analyze/etc.) the file
    must be copied to the root. Drift between the two copies is a
    silent production hazard, because the scheduled tasks run the root
    copy but Cowork edits land in ``engine/``.
  - File length floor — each file is at least 1,000 bytes. A sub-1KB
    run_picks.py is never legitimate.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

# Files that MUST end in the canonical ``if __name__ == "__main__": main()``
# block, in both the ``engine/`` source and the repo-root mirror.
CRITICAL_FILES = [
    "run_picks.py",
    "grade_picks.py",
    "analyze_picks.py",
    "morning_preview.py",
    "weekly_recap.py",
]

CANONICAL_TAIL = 'if __name__ == "__main__":\n    main()\n'

# Minimum reasonable size. run_picks.py is ~5k lines (~200 KB); a file
# under 1 KB is almost certainly truncated.
MIN_BYTES = 1_000


def _both_copies(name: str) -> list[Path]:
    """Return the engine/ copy and the root-mirror copy of ``name``."""
    return [HERE / "engine" / name, HERE / name]


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_tail_is_canonical_entrypoint(filename):
    """Both the engine/ copy and the root mirror must end with the
    standard main-guard block, including a trailing newline.
    """
    for path in _both_copies(filename):
        assert path.exists(), f"Missing file: {path}"
        text = path.read_text(encoding="utf-8")
        assert text.endswith(CANONICAL_TAIL), (
            f"{path} does not end with the canonical entrypoint.\n"
            f"Last 120 bytes:\n{text[-120:]!r}\n"
            f"Expected tail:\n{CANONICAL_TAIL!r}"
        )


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_file_ends_with_newline(filename):
    """No ``\\ No newline at end of file``. This has bitten run_picks.py
    at least twice — once the tail was lopped, once a heredoc forgot
    the terminal newline. Either way, a missing trailing \\n is a red
    flag that something truncated the file.
    """
    for path in _both_copies(filename):
        assert path.exists(), f"Missing file: {path}"
        data = path.read_bytes()
        assert data.endswith(b"\n"), (
            f"{path} does not end with a newline — likely truncated. "
            f"Last 40 bytes: {data[-40:]!r}"
        )


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_file_is_not_suspiciously_small(filename):
    """A run_picks.py under 1 KB is never legitimate. Catches the
    degenerate case where a Write clobber produces a near-empty file
    that still happens to end in ``main()\\n`` (because somebody
    concatenated just the tail).
    """
    for path in _both_copies(filename):
        assert path.exists(), f"Missing file: {path}"
        size = path.stat().st_size
        assert size >= MIN_BYTES, (
            f"{path} is only {size} bytes. "
            f"Minimum expected is {MIN_BYTES}. Truncation suspected."
        )


@pytest.mark.parametrize("filename", CRITICAL_FILES)
def test_engine_and_root_copies_are_identical(filename):
    """CLAUDE.md: 'Always sync to root after edits (cp engine/run_picks.py
    run_picks.py)'. If the two copies diverge, scheduled Windows tasks
    (which run the root copy) execute a different binary than anything
    pytest / Cowork sees.

    This catches the classic split-brain: fix applied to engine/,
    forgotten at root.
    """
    engine_path, root_path = _both_copies(filename)
    assert engine_path.exists(), f"Missing: {engine_path}"
    assert root_path.exists(), f"Missing: {root_path}"

    engine_md5 = hashlib.md5(engine_path.read_bytes()).hexdigest()
    root_md5 = hashlib.md5(root_path.read_bytes()).hexdigest()

    assert engine_md5 == root_md5, (
        f"engine/{filename} and {filename} have drifted.\n"
        f"  engine/ md5: {engine_md5}\n"
        f"  root    md5: {root_md5}\n"
        f"Run: cp engine/{filename} {filename}"
    )
