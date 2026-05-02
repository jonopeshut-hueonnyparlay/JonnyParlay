"""Regression tests for Section 33 — bootstrap script hardening.

Audit findings closed here (Apr 20 2026):
    M-6  go.ps1 forces UTF-8 console encoding so emoji / box-drawing
         characters in Python stdout don't crash the run.
    M-8  preflight.bat verifies/installs openpyxl (needed for weekly_recap
         xlsx attachment — previously a silent skip).
    M-9  go.ps1 $depMap includes openpyxl (mirror of preflight.bat).
    M-18 go.ps1 SaberSim CSV wait-timeout now exits 2 (not break→exit 0)
         so Task Scheduler flags the failure instead of silently succeeding.

These tests are source-search tests: the shell scripts aren't pytest-
executable, so we grep for the required tokens + ordering invariants. The
patterns deliberately allow whitespace and comment variance — they verify
INTENT, not exact byte sequences.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GO_PS1 = REPO_ROOT / "go.ps1"
PREFLIGHT_BAT = REPO_ROOT / "preflight.bat"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def go_src() -> str:
    assert GO_PS1.exists(), f"go.ps1 missing at {GO_PS1}"
    return GO_PS1.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def preflight_src() -> str:
    assert PREFLIGHT_BAT.exists(), f"preflight.bat missing at {PREFLIGHT_BAT}"
    # preflight.bat is ASCII + a few unicode dash glyphs — read utf-8 with
    # errors="replace" so a stray cp1252 byte never breaks the test run.
    return PREFLIGHT_BAT.read_text(encoding="utf-8", errors="replace")


# ── M-6: go.ps1 sets UTF-8 console encoding ─────────────────────────────────

def test_go_ps1_sets_console_output_encoding_to_utf8(go_src: str):
    """Claude audit M-6: emoji + box chars in Python stdout must not crash
    under the default cp1252 console. Fix is to flip OutputEncoding to UTF-8
    at script start."""
    assert re.search(
        r"\[Console\]::OutputEncoding\s*=\s*\[System\.Text\.Encoding\]::UTF8",
        go_src,
    ), "go.ps1 must set [Console]::OutputEncoding = [System.Text.Encoding]::UTF8"


def test_go_ps1_sets_outputencoding_for_pipeline(go_src: str):
    """$OutputEncoding (PowerShell-side) must ALSO be UTF-8 — otherwise
    piping to external processes re-encodes to cp1252 and defeats the fix."""
    assert re.search(
        r"\$OutputEncoding\s*=\s*\[System\.Text\.Encoding\]::UTF8",
        go_src,
    ), "go.ps1 must set $OutputEncoding = [System.Text.Encoding]::UTF8"


def test_go_ps1_utf8_setup_is_near_top(go_src: str):
    """The encoding flip must happen BEFORE any Write-Host call emits output
    — otherwise early banners go through cp1252 and the fix is a no-op for
    the lines that matter most."""
    enc_idx = go_src.find("[Console]::OutputEncoding")
    first_write = go_src.find("Write-Host")
    assert enc_idx != -1, "no OutputEncoding assignment found"
    assert first_write != -1, "no Write-Host found (script malformed?)"
    # The function definition for Write-Hdr / Write-Host wrappers is earlier
    # in the file; we only care that the FIRST actual CALL of any Write-Host
    # statement happens after encoding setup. Find the first Write-Host
    # that's actually invoking (not defining), which is inside Write-Hdr body
    # or the banner. Simpler check: encoding block must come before the
    # "Write-Hdr \"JonnyParlay" banner line, which is the first invocation.
    banner_idx = go_src.find('Write-Hdr "JonnyParlay')
    assert banner_idx != -1, "opening banner not found"
    assert enc_idx < banner_idx, (
        "UTF-8 setup must precede the opening Write-Hdr banner — "
        "otherwise early output goes through cp1252."
    )


def test_go_ps1_utf8_setup_is_guarded(go_src: str):
    """Non-fatal if the host rejects the assignment (ISE, very old PS).
    We require a try/catch wrapper so a picky host doesn't abort the run."""
    # Look for the encoding assignment inside a try {...} catch {...} block.
    # Find the index of the encoding line, then walk backward for 'try {'.
    m = re.search(r"\[Console\]::OutputEncoding", go_src)
    assert m, "encoding assignment missing"
    prefix = go_src[: m.start()]
    # The nearest preceding `try {` should be within 400 chars — tight window
    # to catch accidental try-block removal.
    last_try = prefix.rfind("try {")
    assert last_try != -1 and (m.start() - last_try) < 400, (
        "UTF-8 assignment should be wrapped in try { ... } catch { ... } "
        "so a picky PS host doesn't crash the run."
    )


# ── M-8: preflight.bat verifies openpyxl ─────────────────────────────────────

def test_preflight_bat_checks_openpyxl_import(preflight_src: str):
    """weekly_recap.py needs openpyxl for its xlsx attachment. Previously a
    silent soft-dep — recap shipped without the spreadsheet. Now preflight
    fails loudly if it's missing."""
    assert re.search(
        r'python\s+-c\s+"import\s+openpyxl"',
        preflight_src,
    ), "preflight.bat must run `python -c \"import openpyxl\"`"


def test_preflight_bat_auto_installs_openpyxl_on_miss(preflight_src: str):
    """If the import fails, preflight must offer to install it — matching
    the filelock/requests/pillow pattern. Otherwise the check is toothless."""
    assert re.search(
        r"pip\s+install\s+openpyxl\s+--break-system-packages",
        preflight_src,
    ), "preflight.bat must auto-install openpyxl on miss (with --break-system-packages)"


def test_preflight_bat_openpyxl_check_is_before_required_files(preflight_src: str):
    """Ordering contract: dep checks (steps 1-5) run BEFORE file-existence
    checks. If the engine imports openpyxl at startup (it doesn't today, but
    might tomorrow), we want the install to have already happened."""
    openpyxl_idx = preflight_src.find('import openpyxl')
    # The required-files block is identified by its check for run_picks.py
    # inside a `for %%F in (...)` loop.
    required_block = re.search(
        r"for\s+%%F\s+in\s+\(run_picks\.py", preflight_src,
    )
    assert openpyxl_idx != -1, "openpyxl check missing"
    assert required_block, "required-files block not found"
    assert openpyxl_idx < required_block.start(), (
        "openpyxl check must run before required-files check — "
        "dep verification precedes file sanity."
    )


def test_preflight_bat_openpyxl_check_is_after_pillow(preflight_src: str):
    """The four install-on-miss checks (filelock → requests → pillow →
    openpyxl) share a visual pattern. openpyxl should come last in the dep
    group so existing muscle-memory for earlier steps still works."""
    pillow_idx = preflight_src.find("import PIL")
    openpyxl_idx = preflight_src.find("import openpyxl")
    assert pillow_idx != -1, "pillow check missing from preflight.bat"
    assert openpyxl_idx != -1, "openpyxl check missing from preflight.bat"
    assert pillow_idx < openpyxl_idx, (
        "openpyxl check should come after the pillow check, "
        "matching the filelock → requests → pillow → openpyxl order."
    )


# ── M-9: go.ps1 $depMap includes openpyxl ───────────────────────────────────

def test_go_ps1_depmap_includes_openpyxl(go_src: str):
    """Mirror of M-8 in PowerShell. $depMap drives the dependency install
    loop; leaving openpyxl out means the loop never touches it."""
    # Find the $depMap assignment (may span one line); must contain the
    # openpyxl → openpyxl mapping.
    m = re.search(r"\$depMap\s*=\s*@\{([^}]*)\}", go_src, re.DOTALL)
    assert m, "could not find $depMap = @{ ... } in go.ps1"
    dep_block = m.group(1)
    assert re.search(r'"openpyxl"\s*=\s*"openpyxl"', dep_block), (
        "go.ps1 $depMap is missing the \"openpyxl\"=\"openpyxl\" entry — "
        "weekly_recap xlsx attachment will silently break on fresh Windows boxes."
    )


def test_go_ps1_depmap_still_has_existing_deps(go_src: str):
    """Belt-and-suspenders: the M-9 fix must not have accidentally dropped
    filelock / requests / pillow from the map."""
    m = re.search(r"\$depMap\s*=\s*@\{([^}]*)\}", go_src, re.DOTALL)
    assert m
    dep_block = m.group(1)
    for pair in ['"filelock"="filelock"', '"requests"="requests"', '"PIL"="pillow"']:
        # Tolerate whitespace variance around the `=`.
        pattern = pair.replace("=", r"\s*=\s*")
        assert re.search(pattern, dep_block), (
            f"go.ps1 $depMap is missing entry matching {pair!r}"
        )


# ── M-18: SaberSim CSV wait timeout exits 2, not break ──────────────────────

def test_go_ps1_sabersim_wait_timeout_exits_nonzero(go_src: str):
    """Previous code did `Write-Warn ... ; break`, which fell through to
    the rest of the script and emitted exit-0 on empty. Task Scheduler
    doesn't flag exit-0. Fix: `exit 2` inside the timeout branch."""
    # Isolate the 15-minute timeout block — it's the only place this
    # exact TotalMinutes > 15 check appears.
    m = re.search(
        r"TotalMinutes\s*-gt\s*15\s*\)\s*\{([^}]+)\}",
        go_src,
        re.DOTALL,
    )
    assert m, "15-minute SaberSim wait timeout block not found"
    branch = m.group(1)
    assert re.search(r"\bexit\s+2\b", branch), (
        "SaberSim timeout branch must `exit 2` — a bare `break` lets the "
        "script fall through and return exit-0, which Task Scheduler reads "
        "as success."
    )


def test_go_ps1_sabersim_timeout_no_longer_uses_bare_break(go_src: str):
    """The old implementation ended with `break` — verify it's gone so a
    future merge conflict doesn't reintroduce the silent-success bug."""
    m = re.search(
        r"TotalMinutes\s*-gt\s*15\s*\)\s*\{([^}]+)\}",
        go_src,
        re.DOTALL,
    )
    assert m
    branch = m.group(1)
    # Strip PowerShell `#` comments so the audit-note text (which mentions
    # "`break`") doesn't trip the token scan. PowerShell treats everything
    # after an unquoted `#` to end-of-line as a comment.
    code_only_lines = []
    for raw in branch.splitlines():
        idx = raw.find("#")
        if idx != -1:
            raw = raw[:idx]
        code_only_lines.append(raw)
    code_only = "\n".join(code_only_lines)
    tokens = re.findall(r"\b\w+\b", code_only)
    assert "break" not in tokens, (
        "SaberSim timeout branch must not contain a bare `break` anymore — "
        "use `exit 2` so the run surfaces as a failure."
    )


def test_go_ps1_sabersim_timeout_prompts_before_exit(go_src: str):
    """Quality-of-life: the user should see a pause before the window
    closes. Matches the pattern used by the other fatal-error exit paths
    (Python-missing, files-missing)."""
    m = re.search(
        r"TotalMinutes\s*-gt\s*15\s*\)\s*\{([^}]+)\}",
        go_src,
        re.DOTALL,
    )
    assert m
    branch = m.group(1)
    assert "Read-Host" in branch, (
        "SaberSim timeout branch should `Read-Host` before exit — matches "
        "the rest of the script's behavior on fatal errors."
    )


# ── Sanity: other sections' contracts are still intact ──────────────────────

def test_go_ps1_no_sync_pairs_s33(go_src: str):
    """H1 (May 1 2026): syncPairs loop removed — root files are L16 runpy shims
    that never drift, so the hash-compare copy loop is gone entirely.
    Complementary to test_section23 checks."""
    assert "$syncPairs = @(" not in go_src, (
        "go.ps1 must not contain $syncPairs array after H1 fix (L16 shim architecture)"
    )
def test_preflight_bat_still_checks_filelock_requests_pillow(preflight_src: str):
    """Regression guard — our step-5 insertion must not have broken the
    earlier dep checks."""
    for tok in ["import filelock", "import requests", "import PIL", "import openpyxl"]:
        assert tok in preflight_src, f"preflight.bat dropped `{tok}` check"
