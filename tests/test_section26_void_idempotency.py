#!/usr/bin/env python3
"""Regression tests for Section 26 — audit M-23.

VOID is a terminal grader state. Once a row is graded W / L / P / VOID the
grader must never re-fetch boxscores, re-grade, or overwrite the row on a
subsequent invocation — and the ROI denominator must exclude both P and
VOID so a voided pick doesn't inflate `risked` and deflate ROI.

Covers:

  grade_picks.TERMINAL_RESULTS              canonical terminal-state set.
  grade_picks._is_terminal_result           case/whitespace/None tolerance.
  grade_picks ungraded filter               VOID rows skipped on 2nd run.
  grade_picks defensive guard               refuses to overwrite terminal.
  grade_picks _atomic_write_rows            VOID survives a round trip.
  results_graphic.daily_stats               VOID excluded from risked (M-23
                                            parallel of weekly_recap H-5).

Related tests already covering adjacent surface:
  * test_section21_grader.py — compute_pl(VOID) == 0 parity and
    weekly_recap.daily_stats VOID handling (audit H-5).
  * test_section21_grader.py — MLB DNP → grade_prop returns 'VOID'.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# TERMINAL_RESULTS + _is_terminal_result helper
# ─────────────────────────────────────────────────────────────────

def test_terminal_results_is_exactly_w_l_p_void():
    """Audit M-23: the set of terminal grader states is W / L / P / VOID.

    If this ever changes, every site that asks "is this pick done?" — the
    ungraded filter, the idempotency guard, the refund bucket in
    weekly_recap + results_graphic — must be audited in lockstep.
    """
    from grade_picks import TERMINAL_RESULTS
    assert TERMINAL_RESULTS == frozenset({"W", "L", "P", "VOID"})


@pytest.mark.parametrize("raw,expected", [
    ("W", True),
    ("L", True),
    ("P", True),
    ("VOID", True),
    ("void", True),
    ("Void", True),
    ("  VOID  ", True),
    ("\tW\n", True),
    ("", False),
    (None, False),
    ("   ", False),
    ("PENDING", False),
    ("X", False),
    ("WIN", False),   # only exact tokens count as terminal
])
def test_is_terminal_result_is_case_and_whitespace_tolerant(raw, expected):
    """The helper must be tolerant of whitespace, case, and None because
    real-world pick_log rows pick up all of the above from manual edits,
    CSV round-trips, and empty writes.
    """
    from grade_picks import _is_terminal_result
    assert _is_terminal_result(raw) is expected


# ─────────────────────────────────────────────────────────────────
# ungraded filter — VOID is terminal on the 2nd grader run
# ─────────────────────────────────────────────────────────────────

def test_ungraded_filter_uses_inverse_of_terminal_results():
    """Source-level contract: the ungraded filter in grade_picks must be the
    inverse of _is_terminal_result / TERMINAL_RESULTS, not a bare
    ``result == ""`` check. That way a new grader state (e.g. "PENDING") can't
    silently slip through.
    """
    src = (HERE.parent / "engine" / "grade_picks.py").read_text(encoding="utf-8")
    # The single ungraded-building loop should be using the helper now.
    assert "if not _is_terminal_result(row.get(\"result\")):" in src, (
        "ungraded filter must use _is_terminal_result(row.get('result')) — "
        "a bare 'result == \"\"' check lets future terminal values leak through."
    )
    # And the older bare-string check must be gone from that filter.
    # (We don't grep globally — TERMINAL_RESULTS membership may still appear
    # elsewhere for recap gating.)
    assert "(row.get(\"result\") or \"\").strip() == \"\"" not in src, (
        "legacy ungraded filter string survived — M-23 rewrite incomplete."
    )


# ─────────────────────────────────────────────────────────────────
# Defensive idempotency guard
# ─────────────────────────────────────────────────────────────────

def test_defensive_guard_refuses_to_overwrite_terminal_row():
    """Source-level contract: even if the ungraded filter is bypassed, the
    grade-write loop must refuse to clobber an already-terminal row."""
    src = (HERE.parent / "engine" / "grade_picks.py").read_text(encoding="utf-8")
    # Guard checks the existing row's result BEFORE writing.
    assert "existing = rows[idx].get(\"result\")" in src, (
        "M-23 defensive guard missing — grade-write loop doesn't read the "
        "current result before overwriting."
    )
    assert "if _is_terminal_result(existing):" in src, (
        "M-23 defensive guard must short-circuit via _is_terminal_result."
    )
    # And it must emit a visible warning so drift is debuggable.
    assert "M-23 skip:" in src, (
        "Defensive guard must log a warning when it refuses to overwrite, "
        "otherwise silent data drift is possible."
    )


# ─────────────────────────────────────────────────────────────────
# VOID survives a full write/read round-trip through _atomic_write_rows
# ─────────────────────────────────────────────────────────────────

def test_void_round_trips_through_atomic_write_rows(tmp_path):
    """End-to-end: a VOID row written by _atomic_write_rows must come back
    out of the CSV verbatim. If some normalizer coerces VOID to L or ""
    between write and read, every downstream ROI calculation breaks.
    """
    from grade_picks import _atomic_write_rows

    fieldnames = ["date", "player", "stat", "line", "direction",
                  "size", "odds", "result"]
    rows = [
        {"date": "2026-04-19", "player": "Test A", "stat": "AST",
         "line": "6.5", "direction": "over", "size": "1",
         "odds": "-110", "result": "VOID"},
        {"date": "2026-04-19", "player": "Test B", "stat": "PTS",
         "line": "22.5", "direction": "under", "size": "1",
         "odds": "+100", "result": "W"},
        {"date": "2026-04-19", "player": "Test C", "stat": "REB",
         "line": "8.5", "direction": "over", "size": "1",
         "odds": "-115", "result": ""},
    ]
    log_path = tmp_path / "pick_log.csv"
    _atomic_write_rows(str(log_path), fieldnames, rows, lock_timeout=5)

    with open(log_path, newline="", encoding="utf-8") as f:
        reread = list(csv.DictReader(f))

    assert [r["result"] for r in reread] == ["VOID", "W", ""], (
        f"VOID row did not round-trip — got {[r['result'] for r in reread]!r}"
    )


# ─────────────────────────────────────────────────────────────────
# results_graphic.daily_stats — M-23 parallel to weekly_recap H-5
# ─────────────────────────────────────────────────────────────────

def test_results_graphic_daily_stats_excludes_void_from_risked():
    """Before M-23, results_graphic.daily_stats used ``result != 'P'`` as the
    risked filter, so a single VOID pick would count 1u in the denominator
    and deflate the daily ROI shown on the Discord results card.

    Same scenario as the weekly_recap H-5 test:
      * One 1u W @ -110  → net +0.909u
      * One 1u VOID       → net 0

    With the fix, risked = 1u (only the W), ROI ≈ 90.9%.
    With the bug,  risked = 2u, ROI ≈ 45.4%.
    """
    from results_graphic import daily_stats
    picks = [
        {"result": "W",    "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
        {"result": "VOID", "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
    ]
    w, l, pu, pl, roi = daily_stats(picks)
    assert w == 1 and l == 0
    assert pytest.approx(pl, abs=0.01) == 0.91
    assert 85 <= roi <= 95, (
        f"ROI={roi} — if this is ~45, VOID stake is still polluting 'risked' "
        f"in results_graphic (M-23 parallel to weekly_recap H-5)."
    )


def test_results_graphic_daily_stats_excludes_push_and_void():
    """Both refund types (P and VOID) must be excluded from risked. This
    mirrors results_graphic._REFUNDED_RESULTS / weekly_recap._REFUNDED_RESULTS.
    """
    from results_graphic import daily_stats
    picks = [
        {"result": "W",    "size": "1", "odds": "-110"},
        {"result": "P",    "size": "1", "odds": "-110"},
        {"result": "VOID", "size": "1", "odds": "-110"},
    ]
    w, l, pu, pl, roi = daily_stats(picks)
    assert w == 1
    assert pu == 1  # only P is counted in pu; VOID doesn't currently bucket here
    # risked denominator = 1u (only the W). P & VOID are both refunded.
    assert 85 <= roi <= 95, f"ROI={roi} — P or VOID still polluting 'risked'."


def test_results_graphic_handles_lowercase_void():
    """Manual edits sometimes produce 'void' lowercase. The risked filter
    strips + uppers before comparing, so the denominator must still exclude
    a lowercase void row.
    """
    from results_graphic import daily_stats
    picks = [
        {"result": "W",    "size": "1", "odds": "-110"},
        {"result": "void", "size": "1", "odds": "-110"},
    ]
    _, _, _, _, roi = daily_stats(picks)
    assert 85 <= roi <= 95, (
        f"ROI={roi} — lowercase 'void' is not being normalized in the risked "
        f"filter. Expected ~90.9%, got {roi}."
    )


# ─────────────────────────────────────────────────────────────────
# Sanity parity with existing helpers — don't regress H-5
# ─────────────────────────────────────────────────────────────────

def test_weekly_recap_and_results_graphic_refund_sets_match():
    """Audit H-5 (weekly_recap) + audit M-23 (results_graphic) must agree on
    which result tokens are refunded. If one drifts, the Discord daily card
    and the Sunday weekly recap will report different ROIs for the same day.
    """
    from weekly_recap import _REFUNDED_RESULTS as weekly
    from results_graphic import _REFUNDED_RESULTS as graphic
    assert weekly == graphic == frozenset({"P", "VOID"})


def test_terminal_results_is_superset_of_refunded():
    """TERMINAL_RESULTS must contain every refund token — otherwise a VOID
    row could be re-graded (terminal-but-not-refund can't happen in reverse).
    """
    from grade_picks import TERMINAL_RESULTS
    from results_graphic import _REFUNDED_RESULTS
    assert _REFUNDED_RESULTS <= TERMINAL_RESULTS
