#!/usr/bin/env python3
"""Regression tests for Section 23 — observability, sync hygiene, xlsx cap.

Covers:
  H-7   weekly_recap.main() and morning_preview.main() exit non-zero when
        the underlying post function returns False. A failed Discord post
        used to exit 0, making Task Scheduler history look identical to a
        successful run — outages were invisible.

  H-12  go.ps1 syncPairs includes analyze_picks.py, so the root mirror
        doesn't silently drift from the engine/ source of truth.

  H-15  build_weekly_xlsx refuses to materialize an unbounded BytesIO —
        callers that accidentally hand it the entire pick_log get a
        truncated workbook + a loud warning rather than an OOM.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# H-7 — CLI exit code on failed Discord post
# ─────────────────────────────────────────────────────────────────

def test_weekly_recap_main_exits_nonzero_on_post_failure(monkeypatch, tmp_path):
    """weekly_recap.main() must exit with a non-zero code when
    post_weekly_recap returns False. Otherwise Task Scheduler marks the
    run green and the operator never sees the outage.
    """
    import weekly_recap

    # Feed main() one non-empty graded pick so we reach the post call.
    fake_pick = {
        "date": "2026-04-13", "sport": "NBA", "player": "Test", "team": "LAL",
        "stat": "PTS", "line": "20.5", "direction": "over", "odds": "-110",
        "book": "draftkings", "tier": "T2", "pick_score": "72",
        "size": "1.0", "mode": "Default", "result": "W",
        "run_type": "primary",
    }
    monkeypatch.setattr(weekly_recap, "load_picks", lambda: [fake_pick])
    monkeypatch.setattr(weekly_recap, "filter_week", lambda rows, m, s: [fake_pick])
    # Force the post to fail.
    monkeypatch.setattr(weekly_recap, "post_weekly_recap",
                        lambda *a, **kw: False)
    # Avoid arg parsing of pytest's argv.
    monkeypatch.setattr(sys, "argv", ["weekly_recap.py", "--test"])

    with pytest.raises(SystemExit) as excinfo:
        weekly_recap.main()
    # Per our convention: 2 = post failed (distinct from 1 = no pick_log,
    # 0 = no picks for the week).
    assert excinfo.value.code == 2, (
        f"H-7: expected exit 2 on post failure, got {excinfo.value.code!r}"
    )


def test_weekly_recap_main_exits_zero_on_post_success(monkeypatch):
    """Sanity: successful post must NOT trigger sys.exit(2)."""
    import weekly_recap

    fake_pick = {
        "date": "2026-04-13", "sport": "NBA", "player": "Test", "team": "LAL",
        "stat": "PTS", "line": "20.5", "direction": "over", "odds": "-110",
        "book": "draftkings", "tier": "T2", "pick_score": "72",
        "size": "1.0", "mode": "Default", "result": "W",
        "run_type": "primary",
    }
    monkeypatch.setattr(weekly_recap, "load_picks", lambda: [fake_pick])
    monkeypatch.setattr(weekly_recap, "filter_week", lambda rows, m, s: [fake_pick])
    monkeypatch.setattr(weekly_recap, "post_weekly_recap",
                        lambda *a, **kw: True)
    monkeypatch.setattr(sys, "argv", ["weekly_recap.py", "--test"])

    # Should return without raising — successful path falls off the end.
    try:
        weekly_recap.main()
    except SystemExit as e:
        # Only 0/None is acceptable on success.
        assert e.code in (0, None), (
            f"H-7: success path must not exit non-zero, got {e.code!r}"
        )


def test_morning_preview_main_exits_nonzero_on_post_failure(monkeypatch):
    """morning_preview.main() mirrors weekly_recap — exit 2 on failed post."""
    import morning_preview

    fake_pick = {
        "date": "2026-04-20", "sport": "NBA", "player": "Test", "team": "LAL",
        "stat": "PTS", "line": "20.5", "direction": "over", "odds": "-110",
        "book": "draftkings", "tier": "T2", "pick_score": "72",
        "size": "1.0", "mode": "Default", "result": "",
        "run_type": "primary",
    }
    monkeypatch.setattr(morning_preview, "load_pick_log", lambda: [fake_pick])
    monkeypatch.setattr(morning_preview, "get_today_picks",
                        lambda rows, date_str: [fake_pick])
    monkeypatch.setattr(morning_preview, "post_morning_preview",
                        lambda *a, **kw: False)
    monkeypatch.setattr(sys, "argv", ["morning_preview.py",
                                       "--date", "2026-04-20",
                                       "--test"])

    with pytest.raises(SystemExit) as excinfo:
        morning_preview.main()
    assert excinfo.value.code == 2, (
        f"H-7: expected exit 2 on post failure, got {excinfo.value.code!r}"
    )


def test_morning_preview_main_exits_zero_on_post_success(monkeypatch):
    import morning_preview

    fake_pick = {
        "date": "2026-04-20", "sport": "NBA", "player": "Test", "team": "LAL",
        "stat": "PTS", "line": "20.5", "direction": "over", "odds": "-110",
        "book": "draftkings", "tier": "T2", "pick_score": "72",
        "size": "1.0", "mode": "Default", "result": "",
        "run_type": "primary",
    }
    monkeypatch.setattr(morning_preview, "load_pick_log", lambda: [fake_pick])
    monkeypatch.setattr(morning_preview, "get_today_picks",
                        lambda rows, date_str: [fake_pick])
    monkeypatch.setattr(morning_preview, "post_morning_preview",
                        lambda *a, **kw: True)
    monkeypatch.setattr(sys, "argv", ["morning_preview.py",
                                       "--date", "2026-04-20",
                                       "--test"])
    try:
        morning_preview.main()
    except SystemExit as e:
        assert e.code in (0, None), (
            f"H-7: success path must not exit non-zero, got {e.code!r}"
        )


def test_h7_banner_printed_on_weekly_failure(monkeypatch, capsys):
    """The operator-visible failure banner must hit stdout. Without the
    banner, a silent sys.exit(2) is technically correct but the person
    staring at the console can't tell what happened.
    """
    import weekly_recap

    fake_pick = {
        "date": "2026-04-13", "sport": "NBA", "player": "Test", "team": "LAL",
        "stat": "PTS", "line": "20.5", "direction": "over", "odds": "-110",
        "book": "draftkings", "tier": "T2", "pick_score": "72",
        "size": "1.0", "mode": "Default", "result": "W",
        "run_type": "primary",
    }
    monkeypatch.setattr(weekly_recap, "load_picks", lambda: [fake_pick])
    monkeypatch.setattr(weekly_recap, "filter_week", lambda rows, m, s: [fake_pick])
    monkeypatch.setattr(weekly_recap, "post_weekly_recap", lambda *a, **kw: False)
    monkeypatch.setattr(sys, "argv", ["weekly_recap.py", "--test"])

    with pytest.raises(SystemExit):
        weekly_recap.main()

    out = capsys.readouterr().out
    assert "H-7" in out and "post failed" in out, (
        f"Expected H-7 banner on stdout, got: {out!r}"
    )


# ─────────────────────────────────────────────────────────────────
# L16 / H1 — go.ps1 must NOT contain a $syncPairs copy loop
# ─────────────────────────────────────────────────────────────────
# L16 (Apr 30 2026): root entry-point files are 5-line runpy shims.
# H1  (May  1 2026): the old $syncPairs loop was removed from go.ps1
# because it overwrote shims with engine source on every run, silently
# reverting the L16 architecture. These tests enforce the correct
# post-L16 state: no copy loop, and the L16 comment present.


def test_go_ps1_no_sync_pairs_array():
    """go.ps1 must NOT contain the $syncPairs array (H1 fix, May 1 2026).
    Root files are permanent shims — they never drift by design, so the
    copy-loop is both unnecessary and actively harmful.
    """
    go_ps1 = HERE.parent / "go.ps1"
    assert go_ps1.exists(), "go.ps1 missing from repo root"
    text = go_ps1.read_text(encoding="utf-8", errors="replace")
    assert "$syncPairs = @(" not in text, (
        "go.ps1 still contains the $syncPairs array. "
        "This loop overwrites L16 root shims with engine source on every run. "
        "Remove it (see H1 in docs/audits/AUDIT_2026-05-01.md)."
    )


def test_go_ps1_no_copy_item_sync_loop():
    """go.ps1 must NOT contain a Copy-Item call that copies engine/ files
    over root shims. Belt-and-suspenders check beyond the array assertion."""
    go_ps1 = HERE.parent / "go.ps1"
    text = go_ps1.read_text(encoding="utf-8", errors="replace")
    # The old loop contained: Copy-Item $eng $root -Force
    # We should not see any Copy-Item that references engine\ paths
    import re
    sync_copy = re.search(r"Copy-Item\s+\$eng\s+\$root", text)
    assert sync_copy is None, (
        "go.ps1 still contains 'Copy-Item $eng $root' — the L16 shim "
        "overwrite loop is present. Remove it (H1 fix)."
    )


def test_go_ps1_l16_comment_present():
    """go.ps1 must document why no sync loop exists (L16 shim architecture)."""
    go_ps1 = HERE.parent / "go.ps1"
    text = go_ps1.read_text(encoding="utf-8", errors="replace")
    assert "L16" in text, (
        "go.ps1 should contain a comment referencing L16 (the shim architecture "
        "decision) so future maintainers understand why there is no sync loop."
    )


# ─────────────────────────────────────────────────────────────────
# H-15 — build_weekly_xlsx row cap
# ─────────────────────────────────────────────────────────────────

def _make_pick(i: int) -> dict:
    return {
        "date": f"2026-04-{(i % 28) + 1:02d}",
        "sport": "NBA",
        "player": f"Player{i}",
        "team": "LAL",
        "stat": "PTS",
        "line": "20.5",
        "direction": "over",
        "odds": "-110",
        "book": "draftkings",
        "tier": "T2",
        "pick_score": "72",
        "size": "1.0",
        "mode": "Default",
        "result": "W" if i % 2 == 0 else "L",
        "run_type": "primary",
        "game": f"LAL @ DEN",
        "win_prob": "0.55",
        "edge": "0.05",
        "proj": "22.0",
        "closing_odds": "",
        "clv": "",
    }


def test_weekly_xlsx_cap_constant_is_sane():
    """The cap must be a positive integer, not arbitrarily huge.
    5000 is big enough that no single week hits it, small enough that
    an accidental full-log dump can't balloon BytesIO past ~50MB.
    """
    import weekly_recap
    cap = weekly_recap.WEEKLY_XLSX_ROW_CAP
    assert isinstance(cap, int)
    assert 1000 <= cap <= 100_000, (
        f"H-15: WEEKLY_XLSX_ROW_CAP={cap} outside sane 1k–100k range"
    )


def test_weekly_xlsx_under_cap_builds_normally(capsys):
    """Small week (<100 rows) must build without any truncation warning."""
    import weekly_recap
    if not weekly_recap._HAS_OPENPYXL:
        pytest.skip("openpyxl not installed — xlsx branch can't run")

    picks = [_make_pick(i) for i in range(50)]
    buf = weekly_recap.build_weekly_xlsx(picks, "2026-04-13", "2026-04-19")
    assert buf is not None
    out = capsys.readouterr().out
    assert "H-15" not in out, (
        f"H-15: cap must be silent under the limit, got warning: {out!r}"
    )


def test_weekly_xlsx_over_cap_truncates_and_warns(capsys, monkeypatch):
    """Hand build_weekly_xlsx more than the cap and verify:
      - The function still returns a BytesIO (we truncate, not fail).
      - A loud H-15 warning hits stdout.
      - The truncated slice is the MOST RECENT rows, not the oldest.
    """
    import weekly_recap
    if not weekly_recap._HAS_OPENPYXL:
        pytest.skip("openpyxl not installed — xlsx branch can't run")

    # Force a small cap so we don't have to build 5001 rows in unit tests.
    monkeypatch.setattr(weekly_recap, "WEEKLY_XLSX_ROW_CAP", 10)

    picks = [_make_pick(i) for i in range(25)]
    buf = weekly_recap.build_weekly_xlsx(picks, "2026-04-13", "2026-04-19")
    assert buf is not None

    out = capsys.readouterr().out
    assert "H-15" in out, f"Expected H-15 warning, got: {out!r}"
    assert "capping" in out or "cap" in out.lower()
    # The warning should say we had 25 rows.
    assert "25" in out


def test_weekly_xlsx_truncation_keeps_most_recent(monkeypatch):
    """When we truncate, we keep the tail (most-recent picks) not the head.
    Old picks are less useful than fresh ones for a weekly recap.
    """
    import weekly_recap
    if not weekly_recap._HAS_OPENPYXL:
        pytest.skip("openpyxl not installed")

    monkeypatch.setattr(weekly_recap, "WEEKLY_XLSX_ROW_CAP", 5)

    # Give each pick a distinct player name so we can identify which survived.
    picks = []
    for i in range(12):
        p = _make_pick(i)
        p["player"] = f"Keep{i:02d}" if i >= 7 else f"Drop{i:02d}"
        picks.append(p)

    buf = weekly_recap.build_weekly_xlsx(picks, "2026-04-13", "2026-04-19")
    assert buf is not None

    # Read the resulting xlsx and confirm the 5 "Keep" rows are present
    # and the 7 "Drop" rows are not.
    import openpyxl
    buf.seek(0)
    wb = openpyxl.load_workbook(buf)
    ws = wb.active
    cells = [str(c.value or "") for row in ws.iter_rows(values_only=False)
             for c in row]
    # The workbook renders player labels in upper-case via _pick_short_label,
    # so normalize the haystack before membership checks.
    joined = " ".join(cells).upper()

    for i in range(7):
        assert f"DROP{i:02d}" not in joined, (
            f"H-15: oldest pick Drop{i:02d} should have been truncated, "
            f"but it's still in the workbook."
        )
    for i in range(7, 12):
        assert f"KEEP{i:02d}" in joined, (
            f"H-15: most-recent pick Keep{i:02d} should have survived truncation."
        )


def test_weekly_xlsx_at_exactly_cap_no_warning(capsys, monkeypatch):
    """Edge case: exactly WEEKLY_XLSX_ROW_CAP rows — no truncation, no warn."""
    import weekly_recap
    if not weekly_recap._HAS_OPENPYXL:
        pytest.skip("openpyxl not installed")

    monkeypatch.setattr(weekly_recap, "WEEKLY_XLSX_ROW_CAP", 10)

    picks = [_make_pick(i) for i in range(10)]
    buf = weekly_recap.build_weekly_xlsx(picks, "2026-04-13", "2026-04-19")
    assert buf is not None
    out = capsys.readouterr().out
    assert "H-15" not in out, (
        f"At exactly the cap, no warning should fire. Got: {out!r}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
