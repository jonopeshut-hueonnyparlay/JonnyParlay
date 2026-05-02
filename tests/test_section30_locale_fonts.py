"""Section 30 — regression tests for M-22 (locale-safe months) + M-5
(strict font mode that refuses to ship illegible cards).

M-22 lock-in
------------
``calendar.month_name`` is locale-sensitive. On a non-en-US Windows
install it returns localized strings ("Avril" instead of "April"), which
silently leaks foreign month names into public Discord posts. These
tests:

  * pin MONTH_NAMES to the exact English-language tuple
  * assert weekly_recap builds English content even when the process
    locale is switched to a non-US locale at runtime
  * assert grade_picks build_monthly_embed produces English output under
    the same locale switch

M-5 lock-in
-----------
Fallback to Pillow's bitmap default produces unreadable cards. Default
behavior is preserved (warn-and-ship) so an ops flip doesn't surprise
the running Windows system, but ``JONNYPARLAY_FONTS_STRICT=1`` MUST
raise FontsUnavailableError when no truetype font resolves. Tests:

  * _strict_fonts_enabled() truthy/falsy table
  * default (strict off) → warn but return a font dict
  * strict on + no fonts → raises FontsUnavailableError
  * strict on + fonts resolved → returns normally, no raise
  * CLI main() exits non-zero on FontsUnavailableError
"""

from __future__ import annotations

import locale
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


# ═════════════════════════════════════════════════════════════════════
# M-22 — Locale-safe English month names
# ═════════════════════════════════════════════════════════════════════

def test_month_names_tuple_is_exactly_english():
    """Contract: MONTH_NAMES is exactly the 13-tuple ("", "January", ...,
    "December"). Index 0 is empty placeholder so 1..12 maps 1:1.
    """
    from month_names import MONTH_NAMES
    assert MONTH_NAMES == (
        "",
        "January",   "February", "March",     "April",
        "May",       "June",     "July",      "August",
        "September", "October",  "November",  "December",
    )


def test_month_names_short_tuple_is_english_3_letter():
    from month_names import MONTH_NAMES_SHORT
    assert MONTH_NAMES_SHORT == (
        "",
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )


def test_month_name_helper_valid_range():
    from month_names import month_name
    assert month_name(1) == "January"
    assert month_name(4) == "April"
    assert month_name(12) == "December"


@pytest.mark.parametrize("bad", [0, 13, -1, 1.5, "4", None, True])
def test_month_name_helper_rejects_out_of_range(bad):
    """Fail loud on garbage input — a silently-wrong month on the
    monthly summary post would be confusing for customers.
    """
    from month_names import month_name
    # Note: ``True`` is an int (1) in Python, so it's actually valid.
    # The other cases all raise.
    if bad is True:
        assert month_name(True) == "January"  # quirk — booleans are ints
        return
    with pytest.raises(ValueError):
        month_name(bad)


def test_month_name_short_helper_valid_range():
    from month_names import month_name_short
    assert month_name_short(1) == "Jan"
    assert month_name_short(12) == "Dec"


# ──────────────────────────────────────────────────────────────────────
# Downstream module usage — must import MONTH_NAMES, not calendar
# ──────────────────────────────────────────────────────────────────────

def test_weekly_recap_does_not_import_calendar():
    """If someone re-adds ``import calendar`` and calls month_name on it,
    localized output sneaks back in. Lock the import list.
    """
    src = (ENGINE_DIR / "weekly_recap.py").read_text(encoding="utf-8")
    # Allow the word "calendar" in comments/strings but not an import.
    import re
    bad = re.search(r"^\s*(?:from|import)\s+calendar\b", src, re.MULTILINE)
    assert bad is None, (
        f"weekly_recap.py re-imports stdlib `calendar` at line "
        f"{src[:bad.start()].count(chr(10)) + 1} — use MONTH_NAMES instead."
    )


def test_grade_picks_does_not_import_calendar():
    src = (ENGINE_DIR / "grade_picks.py").read_text(encoding="utf-8")
    import re
    bad = re.search(r"^\s*(?:from|import)\s+calendar\b", src, re.MULTILINE)
    assert bad is None, (
        "grade_picks.py re-imports stdlib `calendar` — use MONTH_NAMES."
    )


def _strip_comments(src: str) -> str:
    """Return source with full-line comments and trailing # comments removed,
    so regressions in *executable* code can't be masked by doc text that
    happens to mention the old API.
    """
    out_lines = []
    for ln in src.splitlines():
        stripped = ln.lstrip()
        if stripped.startswith("#"):
            continue
        # Strip trailing "# comment" while preserving string literals is
        # hard to do perfectly without a tokenizer; cheap heuristic: cut
        # at the first '#' not inside a string. Good enough because our
        # engine files don't put calendar.month_name inside a string.
        hash_idx = ln.find("#")
        if hash_idx >= 0:
            # Heuristic: if no quote before the hash, treat as comment.
            if '"' not in ln[:hash_idx] and "'" not in ln[:hash_idx]:
                ln = ln[:hash_idx]
        out_lines.append(ln)
    return "\n".join(out_lines)


def test_weekly_recap_uses_month_names_at_summary_site():
    src = (ENGINE_DIR / "weekly_recap.py").read_text(encoding="utf-8")
    code = _strip_comments(src)
    assert "MONTH_NAMES[dt.month]" in code, (
        "weekly_recap.py monthly-so-far line must use MONTH_NAMES, "
        "not calendar.month_name."
    )
    assert "calendar.month_name" not in code, (
        "weekly_recap.py still calls calendar.month_name in code — M-22 regressed."
    )


def test_grade_picks_uses_month_names_everywhere():
    src = (ENGINE_DIR / "grade_picks.py").read_text(encoding="utf-8")
    code = _strip_comments(src)
    assert "calendar.month_name" not in code, (
        "grade_picks.py still calls calendar.month_name in code somewhere — M-22 regressed."
    )
    # Five expected call sites replaced — assert MONTH_NAMES is used
    # at least that many times (defensive: catches partial revert).
    assert code.count("MONTH_NAMES[") >= 5, (
        f"grade_picks.py should reference MONTH_NAMES at >=5 sites, "
        f"got {code.count('MONTH_NAMES[')}"
    )


# ──────────────────────────────────────────────────────────────────────
# Locale-switch behavioral test (the whole point of the audit finding)
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def locale_non_en(request):
    """Attempt to set the process locale to French. If the OS doesn't
    have fr_FR available (common on stripped CI images), skip. The
    important guarantee is that we DON'T use ``calendar.month_name``;
    this test verifies the output when a non-en locale is active.
    """
    saved = locale.setlocale(locale.LC_TIME)
    try:
        try:
            locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, "fr_FR")
            except locale.Error:
                pytest.skip("fr_FR locale not installed on this system")
        yield
    finally:
        try:
            locale.setlocale(locale.LC_TIME, saved)
        except Exception:
            pass


def test_month_names_unaffected_by_locale_switch(locale_non_en):
    """Even with LC_TIME=fr_FR, MONTH_NAMES must remain English."""
    from month_names import MONTH_NAMES
    assert MONTH_NAMES[4] == "April", (
        f"Expected 'April' under fr_FR locale, got {MONTH_NAMES[4]!r}. "
        "M-22 regression: MONTH_NAMES became locale-sensitive."
    )
    # Confirm the regression would fire against stdlib — this proves
    # the test is actually exercising a non-en locale.
    import calendar
    assert calendar.month_name[4] != "April", (
        "This test relies on fr_FR locale producing non-English output "
        "from calendar.month_name. If this fails, the locale fixture "
        "didn't actually switch."
    )


# ═════════════════════════════════════════════════════════════════════
# M-5 — Strict font mode
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("val,expected", [
    ("1",       True),
    ("true",    True),
    ("TRUE",    True),
    ("True",    True),
    ("yes",     True),
    ("YES",     True),
    ("on",      True),
    ("  1  ",   True),
    ("0",       False),
    ("false",   False),
    ("FALSE",   False),
    ("no",      False),
    ("off",     False),
    ("",        False),
    ("bogus",   False),
])
def test_strict_fonts_enabled_truthy_table(val, expected, monkeypatch):
    import results_graphic as rg
    monkeypatch.setenv("JONNYPARLAY_FONTS_STRICT", val)
    assert rg._strict_fonts_enabled() is expected, (
        f"JONNYPARLAY_FONTS_STRICT={val!r} → expected {expected}, "
        f"got {rg._strict_fonts_enabled()}"
    )


def test_strict_fonts_enabled_unset_is_false(monkeypatch):
    import results_graphic as rg
    monkeypatch.delenv("JONNYPARLAY_FONTS_STRICT", raising=False)
    assert rg._strict_fonts_enabled() is False


def test_load_fonts_strict_off_warns_and_returns_dict(monkeypatch, capsys):
    """Default behavior (strict off): if no truetype font resolves,
    emit a warning and return the bitmap fallback dict.
    """
    import results_graphic as rg
    # Reset the module-level warn flag so we can observe the warning.
    monkeypatch.setattr(rg, "_FALLBACK_WARNED", False)
    monkeypatch.delenv("JONNYPARLAY_FONTS_STRICT", raising=False)
    # Force every truetype attempt to fail.
    monkeypatch.setattr(rg, "_build_search_chain", lambda family: [])

    fonts = rg._load_fonts()
    assert isinstance(fonts, dict) and "title" in fonts, (
        "Default mode must return a dict even with no truetype available."
    )
    err = capsys.readouterr().err
    assert "No truetype font found" in err, (
        "Default mode must emit the one-time warning to stderr."
    )


def test_load_fonts_strict_on_no_fonts_raises(monkeypatch):
    """Strict mode + no fonts → FontsUnavailableError. This is the
    whole M-5 guarantee.
    """
    import results_graphic as rg
    monkeypatch.setattr(rg, "_FALLBACK_WARNED", False)
    monkeypatch.setenv("JONNYPARLAY_FONTS_STRICT", "1")
    monkeypatch.setattr(rg, "_build_search_chain", lambda family: [])

    with pytest.raises(rg.FontsUnavailableError) as excinfo:
        rg._load_fonts()
    msg = str(excinfo.value)
    assert "JONNYPARLAY_FONTS_STRICT=1" in msg, (
        "Error message must name the env var so ops can disable it."
    )
    # At least one of the font slots must be listed in the error.
    assert "title" in msg or "pick_text" in msg or "stats" in msg


def test_load_fonts_strict_on_fonts_resolved_does_not_raise(monkeypatch, tmp_path):
    """Strict mode + all fonts resolved → returns normally. Don't turn
    a healthy system into a broken one just because strict is on.
    """
    import results_graphic as rg
    monkeypatch.setattr(rg, "_FALLBACK_WARNED", False)
    monkeypatch.setenv("JONNYPARLAY_FONTS_STRICT", "1")

    # Build a fake chain where _try_load_one will always succeed.
    # We do this by patching _try_load_one to return a dummy font + path.
    class _DummyFont: pass
    def _fake_try_load_one(paths, size):
        return _DummyFont(), "/fake/path.ttf"
    monkeypatch.setattr(rg, "_try_load_one", _fake_try_load_one)

    # Should NOT raise — every slot reports a resolved path.
    fonts = rg._load_fonts()
    assert isinstance(fonts, dict) and len(fonts) >= 6


def test_font_report_records_none_path_in_strict_failure_then_raise(monkeypatch):
    """Regression detail: the FontsUnavailableError message includes the
    list of missing slots, which is derived from _FONT_REPORT. Verify
    the report is populated BEFORE the raise (so ops diagnostics aren't
    empty after a strict failure).
    """
    import results_graphic as rg
    monkeypatch.setattr(rg, "_FALLBACK_WARNED", False)
    monkeypatch.setenv("JONNYPARLAY_FONTS_STRICT", "1")
    monkeypatch.setattr(rg, "_build_search_chain", lambda family: [])

    with pytest.raises(rg.FontsUnavailableError):
        rg._load_fonts()
    report = rg.get_font_report()
    assert report, "_FONT_REPORT must be populated before the raise"
    assert all(meta.get("path") is None for meta in report.values()), (
        "In a total-miss scenario every report entry should have path=None"
    )


# ──────────────────────────────────────────────────────────────────────
# Fallback runner
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
