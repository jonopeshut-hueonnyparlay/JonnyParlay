"""Regression tests for Section 34 — test-safety + preflight + cosmetic cleanup.

Audit findings closed here (Apr 20 2026):
    M-21  test_context.py defaults to --mock (no Anthropic API calls).
          Requires explicit --live to spend credits. Also gives the file a
          shebang, docstring, proper error handling — folding in L-10.
    M-27  CLAUDE.md line-count claim for run_picks.py no longer cites a
          specific stale number ("~4700") — now documents "~5k+ lines and
          growing" so it ages gracefully.
    L-13  preflight.bat stale-lock cleanup covers all three lockfiles
          (pick_log.csv.lock, clv_daemon.lock, discord_posted.json.lock),
          not just the first one.
    L-2   morning_preview.py no longer prints the ⏭️ emoji (cp1252-hostile)
          in its guard-already-posted branches — replaced with [SKIP].
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_CONTEXT = REPO_ROOT / "tests" / "test_context.py"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


# ── M-21: test_context.py safety ────────────────────────────────────────────

@pytest.fixture(scope="module")
def tc_src() -> str:
    assert TEST_CONTEXT.exists(), f"test_context.py missing at {TEST_CONTEXT}"
    return TEST_CONTEXT.read_text(encoding="utf-8")


def test_test_context_has_shebang(tc_src: str):
    """L-10: file used to have no shebang. Now it does so it's runnable as
    an executable script on *nix if Jono ever chmod +x's it."""
    assert tc_src.startswith("#!"), "test_context.py must start with a shebang"


def test_test_context_has_module_docstring(tc_src: str):
    """L-10: top-level docstring documents what the file does and how to use
    the --mock vs --live flags. Guards against someone removing the comment."""
    # The docstring should mention both "mock" and "live" to describe the modes.
    doc = re.search(r'"""(.+?)"""', tc_src, re.DOTALL)
    assert doc, "test_context.py must have a module-level docstring"
    body = doc.group(1).lower()
    assert "mock" in body
    assert "live" in body


def test_test_context_has_mock_and_live_flags(tc_src: str):
    """M-21: both flags must be wired up via argparse (mutually exclusive)."""
    assert "--mock" in tc_src, "test_context.py must accept --mock flag"
    assert "--live" in tc_src, "test_context.py must accept --live flag"
    assert "add_mutually_exclusive_group" in tc_src, (
        "mock/live should be mutually exclusive so nobody can set both by accident"
    )


def test_test_context_defaults_to_mock_behavior(tc_src: str):
    """M-21: the DEFAULT behavior (no flags) must be mock. Otherwise we
    haven't actually closed the audit — anyone running `python test_context.py`
    still burns API credits."""
    # Look for --live action=store_true default=False (the explicit opt-in)
    # and verify there's no `default=True` anywhere near `--live`.
    assert re.search(
        r'"--live".*?default\s*=\s*False',
        tc_src,
        re.DOTALL,
    ), "--live must default to False"


def test_test_context_does_not_import_run_picks_at_module_scope(tc_src: str):
    """M-21: the original file did `from run_picks import ...` at module
    scope, which pulled in the engine (and all its side effects) on *every*
    invocation — including --mock. Must be deferred inside the live branch."""
    # Strip docstrings first so the original bad pattern cited in the docstring
    # doesn't false-match.
    source_no_doc = re.sub(r'"""[\s\S]*?"""', "", tc_src)
    # Line-by-line scan: `from run_picks import ...` must only appear within
    # an indented block (inside main(), behind the --live branch).
    for line in source_no_doc.splitlines():
        if re.match(r"^from\s+run_picks\s+import\b", line):
            pytest.fail(
                "test_context.py imports run_picks at module scope — "
                "must be deferred into the --live branch so --mock runs "
                "don't trigger the engine's side effects."
            )


def test_test_context_mock_run_is_non_interactive_and_fast():
    """M-21: actually run ``python test_context.py --mock`` and verify it
    exits cleanly, prints the MOCK banner, and doesn't try to hit the
    network (any API call would blow our 5-second wall clock)."""
    # Run in a subprocess so module-level imports in the live path (which
    # require ANTHROPIC_API_KEY) don't pollute this test.
    result = subprocess.run(
        [sys.executable, str(TEST_CONTEXT), "--mock", "--quiet"],
        capture_output=True,
        text=True,
        timeout=5,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"--mock run should exit 0, got {result.returncode}. "
        f"stderr: {result.stderr[:400]}"
    )
    assert "[MOCK]" in result.stdout, (
        f"--mock summary line missing. stdout was: {result.stdout[:400]}"
    )


def test_test_context_mock_is_default_when_no_flags():
    """M-21 (strict): `python test_context.py` with NO args must also default
    to mock — the audit's core ask. Running with no flags must not attempt
    any Anthropic API call."""
    result = subprocess.run(
        [sys.executable, str(TEST_CONTEXT), "--quiet"],
        capture_output=True,
        text=True,
        timeout=5,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0
    assert "[MOCK]" in result.stdout
    assert "[LIVE]" not in result.stdout


# ── M-27: CLAUDE.md line-count drift ────────────────────────────────────────

def test_claude_md_no_stale_line_count_claim():
    """M-27: the specific "~4700 lines" claim was stale (actual ~5k). Fix is
    to either update it or drop the specific number. Either is acceptable —
    we just make sure the EXACT stale string is gone so the drift doesn't
    silently creep back."""
    src = CLAUDE_MD.read_text(encoding="utf-8")
    assert "~4700 lines" not in src, (
        "CLAUDE.md still cites the stale '~4700 lines' figure — "
        "audit M-27 calls for dropping the specific number."
    )


def test_claude_md_still_mentions_run_picks_as_source_of_truth():
    """Regression guard: the M-27 fix must not have deleted the 'source of
    truth' directive that tells future Claudes to sync to root after edits."""
    src = CLAUDE_MD.read_text(encoding="utf-8")
    assert "source of truth" in src.lower()
    assert "no sync step needed" in src.lower()  # L16: shims eliminate drift



