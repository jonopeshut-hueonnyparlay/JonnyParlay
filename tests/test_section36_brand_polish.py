"""Regression tests for Section 36 — brand centralization + cosmetic polish.

Audit findings closed here (Apr 21 2026):
    L-7   BRAND_TAGLINE ("edge > everything") moved to engine/brand.py; every
          run_picks/grade_picks/weekly_recap/morning_preview/results_graphic/
          post_nrfi_bonus import it instead of repeating the literal.
    L-1   SPORT_EMOJI map consolidated into brand.py. morning_preview.py's
          old inline dict now re-exports from the canonical map.
    L-6   go.ps1 sets $env:PYTHONIOENCODING = "utf-8" at startup to match
          start_clv_daemon.bat — protects PowerShell-launched engine runs
          from cp1252 crashes on emoji/box-drawing traceback output.
    M-17  weekly_recap clock format is now built via _fmt_clock_et() which
          returns locale-independent, non-zero-padded "H:MM AM/PM ET" —
          consistent with the rest of the codebase's style.
"""

from __future__ import annotations

import importlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent
ENGINE = REPO_ROOT / "engine"
BRAND = ENGINE / "brand.py"
BRAND_ROOT = REPO_ROOT / "brand.py"
GO_PS1 = REPO_ROOT / "go.ps1"
WEEKLY_RECAP = ENGINE / "weekly_recap.py"
MORNING_PREVIEW = ENGINE / "morning_preview.py"
RUN_PICKS = ENGINE / "run_picks.py"
GRADE_PICKS = ENGINE / "grade_picks.py"
RESULTS_GRAPHIC = ENGINE / "results_graphic.py"
POST_NRFI = REPO_ROOT / "post_nrfi_bonus.py"

sys.path.insert(0, str(ENGINE))


# ── L-7: brand module exists and exports the canonical tagline ──────────────

def test_brand_module_exists():
    assert BRAND.exists(), "engine/brand.py must exist (audit L-7)"
    assert BRAND_ROOT.exists(), (
        "root brand.py mirror must exist — run `cp engine/brand.py brand.py`"
    )


def test_brand_module_exports_tagline():
    brand = importlib.import_module("brand")
    assert hasattr(brand, "BRAND_TAGLINE")
    assert brand.BRAND_TAGLINE == "edge > everything", (
        "BRAND_TAGLINE is the canonical picksbyjonny tagline — the ' > ' "
        "must be ASCII greater-than, not Unicode ≻ or »"
    )


def test_brand_module_exports_handle():
    brand = importlib.import_module("brand")
    assert hasattr(brand, "BRAND_HANDLE")
    assert brand.BRAND_HANDLE == "picksbyjonny"


def test_brand_module_has_sport_emoji_map():
    """L-1: consolidated sport-emoji lookup. Every sport referenced elsewhere
    in the engine must be present."""
    brand = importlib.import_module("brand")
    assert hasattr(brand, "SPORT_EMOJI")
    required = {"NBA", "NHL", "NFL", "MLB", "NCAAB", "NCAAF"}
    assert required.issubset(brand.SPORT_EMOJI.keys()), (
        f"SPORT_EMOJI missing required sports: {required - brand.SPORT_EMOJI.keys()}"
    )


def test_brand_module_has_no_side_effects():
    """Importing brand.py must not touch the network, filesystem, env, or
    stdout — it has to be safe to import from hot paths like the CLV daemon."""
    src = BRAND.read_text(encoding="utf-8")
    # No requests, no os.environ writes, no print(), no file I/O at module scope.
    assert "requests" not in src
    assert "print(" not in src
    assert re.search(r"os\.environ\[.*\]\s*=", src) is None
    assert "open(" not in src


def test_brand_root_mirror_matches_engine():
    assert BRAND.read_bytes() == BRAND_ROOT.read_bytes()


# ── L-7: every caller imports BRAND_TAGLINE and drops the literal ───────────

CALLER_FILES: list[tuple[Path, str]] = [
    (RUN_PICKS, "run_picks"),
    (GRADE_PICKS, "grade_picks"),
    (WEEKLY_RECAP, "weekly_recap"),
    (MORNING_PREVIEW, "morning_preview"),
    (RESULTS_GRAPHIC, "results_graphic"),
    (POST_NRFI, "post_nrfi_bonus"),
]


@pytest.mark.parametrize("path,label", CALLER_FILES, ids=[lbl for _, lbl in CALLER_FILES])
def test_caller_imports_brand_tagline(path: Path, label: str):
    """Every caller must import BRAND_TAGLINE from the brand module."""
    src = path.read_text(encoding="utf-8")
    assert re.search(r"from\s+brand\s+import\s+[^\n]*BRAND_TAGLINE", src), (
        f"{label} must import BRAND_TAGLINE from brand.py (audit L-7)"
    )


@pytest.mark.parametrize("path,label", CALLER_FILES, ids=[lbl for _, lbl in CALLER_FILES])
def test_caller_has_no_hardcoded_tagline_in_code(path: Path, label: str):
    """No caller should contain a raw 'edge > everything' literal anywhere
    EXCEPT inside docstrings / comments (documentation is fine, emitted
    strings are not)."""
    src = path.read_text(encoding="utf-8")
    # Strip triple-quoted docstrings and # comments from consideration.
    without_docs = re.sub(r'"""[\s\S]*?"""', "", src)
    without_docs = re.sub(r"'''[\s\S]*?'''", "", without_docs)
    code_only = "\n".join(
        line.split("#", 1)[0] for line in without_docs.splitlines()
    )
    assert "edge > everything" not in code_only, (
        f"{label} still contains a hardcoded 'edge > everything' literal in "
        f"code — replace with BRAND_TAGLINE"
    )


# ── L-1: morning_preview delegates SPORT_EMOJI to brand.py ──────────────────

def test_morning_preview_imports_sport_emoji_from_brand():
    src = MORNING_PREVIEW.read_text(encoding="utf-8")
    assert re.search(
        r"from\s+brand\s+import\s+[^\n]*SPORT_EMOJI",
        src,
    ), "morning_preview.py must import SPORT_EMOJI from brand.py (audit L-1)"


def test_morning_preview_sport_emoji_is_brand_module_map():
    """The local SPORT_EMOJI name must point at brand.SPORT_EMOJI — not a
    copy. Shared identity means a future brand update is picked up without
    another edit here."""
    import brand  # noqa: E402
    morning = importlib.import_module("morning_preview")
    assert morning.SPORT_EMOJI is brand.SPORT_EMOJI, (
        "morning_preview.SPORT_EMOJI must be the same object as brand.SPORT_EMOJI"
    )


# ── L-6: go.ps1 sets PYTHONIOENCODING to utf-8 ──────────────────────────────

@pytest.fixture(scope="module")
def go_src() -> str:
    return GO_PS1.read_text(encoding="utf-8", errors="replace")


def test_go_ps1_sets_pythonioencoding(go_src: str):
    """L-6: matches start_clv_daemon.bat so emoji/box-drawing chars in
    Python tracebacks don't crash with UnicodeEncodeError under PowerShell."""
    assert re.search(
        r'\$env:PYTHONIOENCODING\s*=\s*"utf-8"',
        go_src,
    ), r'go.ps1 must set $env:PYTHONIOENCODING = "utf-8" (audit L-6)'


def test_go_ps1_pythonioencoding_is_before_any_python_call(go_src: str):
    """Env assignment must happen BEFORE the script invokes python.exe —
    otherwise the first child process inherits the wrong encoding."""
    env_idx = go_src.find('$env:PYTHONIOENCODING')
    assert env_idx != -1
    # Find the first actual `python` / `python.exe` invocation (not a
    # comment or string reference).
    py_idx = -1
    for m in re.finditer(r"\bpython(?:\.exe)?\s+", go_src):
        # Cheap comment filter: is this line's leading non-space a `#`?
        line_start = go_src.rfind("\n", 0, m.start()) + 1
        line_head = go_src[line_start:m.start()].lstrip()
        if line_head.startswith("#"):
            continue
        py_idx = m.start()
        break
    if py_idx == -1:
        pytest.skip("no python invocation found in go.ps1 — nothing to order")
    assert env_idx < py_idx, (
        "PYTHONIOENCODING assignment must precede the first python invocation"
    )


# ── M-17: weekly_recap clock format is non-zero-padded and locale-safe ──────

def test_weekly_recap_has_fmt_clock_et_helper():
    src = WEEKLY_RECAP.read_text(encoding="utf-8")
    assert re.search(r"def _fmt_clock_et\s*\(", src), (
        "weekly_recap.py must expose a _fmt_clock_et helper (audit M-17)"
    )


def test_weekly_recap_no_longer_uses_strftime_I_p():
    """The old strftime('%I:%M %p ET') pattern is the bug. It must be gone."""
    src = WEEKLY_RECAP.read_text(encoding="utf-8")
    # Strip docstrings/comments — the audit note *describes* the old pattern.
    without_docs = re.sub(r'"""[\s\S]*?"""', "", src)
    code_only = "\n".join(
        line.split("#", 1)[0] for line in without_docs.splitlines()
    )
    assert "%I:%M %p" not in code_only, (
        "weekly_recap.py still uses strftime('%I:%M %p') — replace with "
        "_fmt_clock_et() for non-zero-padded + locale-safe output"
    )


def test_fmt_clock_et_strips_leading_zero():
    """Functional: 8:35 AM must render as '8:35 AM ET', not '08:35 AM ET'.
    That's the whole reason the helper exists."""
    wr = importlib.import_module("weekly_recap")
    dt = datetime(2026, 4, 21, 8, 35, 0, tzinfo=timezone.utc)
    got = wr._fmt_clock_et(dt)
    assert got == "8:35 AM ET", f"expected '8:35 AM ET', got {got!r}"


def test_fmt_clock_et_handles_noon_midnight_and_pm():
    wr = importlib.import_module("weekly_recap")
    # Noon: 12 PM, not 0 PM.
    noon = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    assert wr._fmt_clock_et(noon) == "12:00 PM ET"
    # Midnight: 12 AM, not 0 AM.
    midnight = datetime(2026, 4, 21, 0, 0, 0, tzinfo=timezone.utc)
    assert wr._fmt_clock_et(midnight) == "12:00 AM ET"
    # PM single-digit hour.
    evening = datetime(2026, 4, 21, 20, 5, 0, tzinfo=timezone.utc)
    assert wr._fmt_clock_et(evening) == "8:05 PM ET"
    # AM with two-digit minute (the 02d preservation).
    early = datetime(2026, 4, 21, 7, 9, 0, tzinfo=timezone.utc)
    assert wr._fmt_clock_et(early) == "7:09 AM ET"


def test_fmt_clock_et_returns_english_ampm_ignoring_locale():
    """Locale-safety check — the helper builds 'AM'/'PM' with string literals,
    so even if the host has LC_ALL=de_DE (which would make strftime('%p')
    emit 'nachm.'), we still get 'PM'."""
    import locale
    wr = importlib.import_module("weekly_recap")
    try:
        # Best-effort attempt to switch locale. If the host doesn't have the
        # locale installed, we just skip — the assertion still proves the
        # current-locale output is English.
        try:
            locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
        except locale.Error:
            pytest.skip("de_DE.UTF-8 locale not available on this host")
        dt = datetime(2026, 4, 21, 20, 30, 0, tzinfo=timezone.utc)
        assert wr._fmt_clock_et(dt) == "8:30 PM ET"
    finally:
        locale.setlocale(locale.LC_TIME, "")


# ── Sync contract ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "engine_name",
    ["run_picks.py", "grade_picks.py", "weekly_recap.py", "morning_preview.py",
     "results_graphic.py", "brand.py"],
)
def test_engine_root_mirror_matches(engine_name: str):
    """Any file edited in this section must have its root mirror in sync."""
    engine_file = ENGINE / engine_name
    root_file = REPO_ROOT / engine_name
    if not root_file.exists():
        pytest.skip(f"no root mirror for {engine_name}")
    assert engine_file.read_bytes() == root_file.read_bytes(), (
        f"{engine_name} engine↔root drift — run "
        f"`cp engine/{engine_name} {engine_name}`"
    )
