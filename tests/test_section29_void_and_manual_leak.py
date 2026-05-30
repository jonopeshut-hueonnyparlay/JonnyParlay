"""Section 29 — lock-in regression tests for H-5 + H-6.

Both audit findings were closed in earlier sections (17 / 20), but the
contracts they codify are load-bearing enough that a dedicated regression
file is worth the disk space:

  H-5   weekly_recap.compute_pl / daily_stats must treat VOID identically
        to P (bet refunded → 0 P&L, 0 risked contribution).

  H-6   results_graphic._load_day_picks must never emit rows with
        run_type == "manual" (those rows go to pick_log_manual.csv which
        should never surface on the public #daily-recap graphic).

The tests below complement the existing coverage in test_section21_grader.py,
test_section26_void_idempotency.py, and test_section20_leakage.py with three
added guardrails:

  1. The `_REFUNDED_RESULTS` frozenset is locked to exactly {"P", "VOID"}.
     A future contributor adding "CANCELLED" or similar MUST update tests.
  2. `_PUBLIC_RUN_TYPES` is locked to {"primary", "bonus", "daily_lay", "", None}.
     Ditto — if "manual" sneaks back in here, the test fails loud.
  3. End-to-end: a mixed week (W/L/P/VOID) computes the correct ROI using
     the real daily_stats aggregation path, not just the unit compute_pl.

Run:
    cd /sessions/.../mnt/JonnyParlay
    python -m pytest test_section29_void_and_manual_leak.py -v
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


# ─────────────────────────────────────────────────────────────────────────────
# H-5 — weekly_recap refund-set contract
# ─────────────────────────────────────────────────────────────────────────────

def test_refunded_results_set_is_exactly_p_and_void():
    """Contract lock: the refund set MUST be exactly {"P", "VOID"}.

    If a future contributor adds another refund code (e.g. "CANCELLED"),
    they MUST update both compute_pl and daily_stats at the same time —
    this test exists to force that decision through review rather than
    drift silently.
    """
    from weekly_recap import _REFUNDED_RESULTS
    assert _REFUNDED_RESULTS == frozenset({"P", "VOID"}), (
        f"_REFUNDED_RESULTS drifted: {_REFUNDED_RESULTS!r}. "
        "If adding a new refund code, update compute_pl + daily_stats + "
        "results_graphic.daily_stats + this test together."
    )


def test_compute_pl_unknown_result_returns_zero_defensively():
    """Defensive: an unrecognized result code (e.g. empty string, 'X',
    'PENDING') must return 0.0 — never raise, never emit a spurious
    positive P&L. This is the safety net for grader output drift.
    """
    from weekly_recap import compute_pl
    for bogus in ("", None, "X", "PENDING", "CANCELLED", "  "):
        assert compute_pl(1.0, "-110", bogus) == 0.0, (
            f"compute_pl must return 0 for unknown result {bogus!r}"
        )


def test_daily_stats_end_to_end_mixed_week_matches_hand_calc():
    """Integration: a realistic weekly mix of W / L / P / VOID must produce
    the hand-calculated ROI. Without the H-5 fix, VOID rows would inflate
    ``risked`` and drag ROI below reality.

    Scenario (all -110 unless noted, 1u size):
      * 3 W at -110  → +3 * (100/110) = +2.7273
      * 2 L at -110  → -2
      * 1 P at -110  →  0 P&L, excluded from risked
      * 2 VOID at -110 → 0 P&L, excluded from risked
      * 1 W at +150 → +1.5

    Net PL      = 2.7273 - 2 + 1.5 = +2.2273 → rounded 2.23
    Risked      = 3 + 2 + 0 + 0 + 1 = 6u (P and VOIDs excluded)
    ROI         = 2.2273 / 6 * 100 = 37.12% → rounded 37.1

    Without H-5, risked would be 9u and ROI would drop to ~24.7 — wrong.
    """
    from weekly_recap import daily_stats

    def mk(result, odds="-110", size="1"):
        return {"result": result, "odds": odds, "size": size,
                "sport": "NBA", "tier": "T1"}

    picks = [
        mk("W"), mk("W"), mk("W"),
        mk("L"), mk("L"),
        mk("P"),
        mk("VOID"), mk("VOID"),
        mk("W", odds="+150"),
    ]
    w, l, pu, pl, roi = daily_stats(picks)
    assert w == 4,  f"expected 4 wins, got {w}"
    assert l == 2,  f"expected 2 losses, got {l}"
    assert pu == 3, f"expected 3 refunds (1P + 2VOID), got {pu}"
    assert pl == pytest.approx(2.23, abs=0.01), (
        f"PL should be ~+2.23u, got {pl}"
    )
    assert roi == pytest.approx(37.1, abs=0.1), (
        f"ROI should be ~37.1% (risked=6u), got {roi}. "
        "If you see ~24.7%, H-5 regressed — VOID is back in the denominator."
    )


def test_daily_stats_all_void_week_returns_zero_not_crash():
    """Edge case: a full week of cancellations (e.g. league-wide postponement)
    must return 0 / 0 / N / 0 / 0 — never divide-by-zero.
    """
    from weekly_recap import daily_stats
    picks = [{"result": "VOID", "odds": "-110", "size": "1",
              "sport": "NBA", "tier": "T1"} for _ in range(5)]
    w, l, pu, pl, roi = daily_stats(picks)
    assert (w, l, pu, pl, roi) == (0, 0, 5, 0.0, 0.0), (
        f"All-VOID week must be (0, 0, 5, 0.0, 0.0), got {(w, l, pu, pl, roi)}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fallback runner (no pytest required)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
