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
PREFLIGHT_BAT = REPO_ROOT / "preflight.bat"
MORNING_PREVIEW = REPO_ROOT / "engine" / "morning_preview.py"
MORNING_PREVIEW_ROOT = REPO_ROOT / "morning_preview.py"
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


# ── L-13: preflight stale-lock cleanup covers all three locks ───────────────

@pytest.fixture(scope="module")
def preflight_src() -> str:
    return PREFLIGHT_BAT.read_text(encoding="utf-8", errors="replace")


def test_preflight_cleans_pick_log_lock(preflight_src: str):
    """The original single-lock cleanup must still be intact."""
    assert "pick_log.csv.lock" in preflight_src


def test_preflight_cleans_clv_daemon_lock(preflight_src: str):
    """L-13: add clv_daemon.lock to the cleanup sweep. A hard-kill of the
    daemon process (power loss, taskkill /F /T) leaves this lockfile behind
    and the next scheduled run can't acquire filelock → silent skip."""
    assert "clv_daemon.lock" in preflight_src, (
        "preflight.bat must also clean data\\clv_daemon.lock"
    )


def test_preflight_cleans_discord_posted_lock(preflight_src: str):
    """L-13: also clean the discord guard lock. Same crash-survival concern."""
    assert "discord_posted.json.lock" in preflight_src, (
        "preflight.bat must also clean data\\discord_posted.json.lock"
    )


def test_preflight_lock_cleanup_uses_single_loop(preflight_src: str):
    """Stylistic: rather than three separate `if exist` blocks, the fix uses
    a single `for %%L in (...)` loop. Check that a loop construct is present
    in the stale-lock section — protects against someone "fixing" it by
    copy-pasting three near-identical blocks."""
    # Slice the file around the "stale lockfiles" comment; verify a `for` loop
    # appears between that header and the next REM header.
    m = re.search(
        r"REM.{0,10}stale lockfiles.*?(?=REM\s+\xe2\x94|REM\s+\xe2\x94\x80\xe2\x94\x80|\Z)",
        preflight_src,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        # Fallback: just find the block by content markers.
        start = preflight_src.lower().find("stale lockfile")
        nxt = preflight_src.lower().find("show today", start)
        if start == -1:
            pytest.fail("'stale lockfiles' header missing from preflight.bat")
        block = preflight_src[start:nxt] if nxt != -1 else preflight_src[start:]
    else:
        block = m.group(0)
    assert re.search(r"for\s+%%\w\s+in\s*\(", block), (
        "stale-lock cleanup should be a single `for %%L in (...)` loop, "
        "not three repeated `if exist` blocks"
    )


# ── L-2: morning_preview no longer prints ⏭️ in console output ──────────────

def test_morning_preview_has_no_skip_emoji_in_prints():
    """L-2: ⏭️ (U+23ED U+FE0F) in a print() crashes on a cp1252 Windows
    console with UnicodeEncodeError, which aborts the whole post path.
    All three call sites must use [SKIP] ASCII instead."""
    src = MORNING_PREVIEW.read_text(encoding="utf-8")
    # Strict: no U+23ED anywhere in the file (even in comments) so the fix
    # is visible in diff reviews.
    assert "\u23ed" not in src, (
        "morning_preview.py still contains the ⏭️ codepoint — "
        "replace all three call sites with [SKIP]"
    )


def test_morning_preview_uses_skip_ascii_marker():
    """Positive check: the replacement marker is actually there, at every
    former ⏭️ site."""
    src = MORNING_PREVIEW.read_text(encoding="utf-8")
    # Count occurrences — we replaced 3 sites in engine/morning_preview.py.
    occurrences = src.count("[SKIP] Morning preview already posted")
    assert occurrences == 3, (
        f"expected 3 [SKIP] occurrences (one per former ⏭️ call site), "
        f"found {occurrences}"
    )


def test_root_morning_preview_mirrors_engine_copy():
    """L16 (Apr 30 2026): root morning_preview.py is a 5-line runpy shim —
    it intentionally differs from engine/morning_preview.py.
    test_tail_guard.py::test_root_shim_delegates_via_runpy guards shim validity.
    The old byte-identical assertion is removed (H1/H2, May 1 2026)."""
    if not MORNING_PREVIEW_ROOT.exists():
        pytest.skip("root morning_preview.py not present in this checkout")
    src = MORNING_PREVIEW_ROOT.read_text(encoding="utf-8", errors="replace")
    assert "runpy.run_module" in src, (
        "root morning_preview.py must be a runpy shim (L16)"
    )
