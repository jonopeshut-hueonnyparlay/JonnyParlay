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
# H-6 — results_graphic public run_type contract
# ─────────────────────────────────────────────────────────────────────────────

def test_public_run_types_does_not_include_manual():
    """Contract lock: "manual" MUST NOT be in _PUBLIC_RUN_TYPES.

    The graphic posts to DISCORD_RECAP_WEBHOOK (public channel). If
    "manual" sneaks in, every manual pick Jono logged silently leaks
    into the public recap — violation of the CLAUDE.md contract
    ("Manual picks never appear in Discord").
    """
    from results_graphic import _PUBLIC_RUN_TYPES
    assert "manual" not in _PUBLIC_RUN_TYPES, (
        "H-6 regression: 'manual' is back in _PUBLIC_RUN_TYPES — manual "
        "picks will leak into the public results graphic."
    )


def test_public_run_types_contract_is_exact():
    """Lock the exact set of allowed run_types on the public graphic.

    If a new public run_type is added (e.g. a future 'killshot' channel
    post), the test must be updated deliberately.
    """
    from results_graphic import _PUBLIC_RUN_TYPES
    assert _PUBLIC_RUN_TYPES == frozenset({"primary", "bonus", "daily_lay", "", None}), (
        f"_PUBLIC_RUN_TYPES drifted: {_PUBLIC_RUN_TYPES!r}. "
        "Update deliberately — new public run_types need matching "
        "downstream handling in weekly_recap.py and grade_picks.py."
    )


def test_load_day_picks_missing_run_type_defaults_to_primary(tmp_path, monkeypatch):
    """Defensive: a legacy row with NO run_type column (pre-migration log)
    must be treated as ``primary`` — not silently dropped.

    The filter uses ``r.get("run_type", "primary")`` so the default fills
    in. If someone changes the default to "" it might still pass (empty
    is in the set), but if they change it to "manual" the row gets
    dropped — this test will catch that.
    """
    from pick_log_schema import CANONICAL_HEADER

    # Write a log where the run_type column exists in the header but is
    # left blank on every row (simulates an older migration).
    log = tmp_path / "pick_log.csv"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
        w.writeheader()
        w.writerow({
            "date": "2026-04-20", "run_time": "10:00", "run_type": "",
            "sport": "NBA", "player": "Legacy Row", "team": "X",
            "stat": "PTS", "line": "20", "direction": "over",
            "odds": "-110", "book": "draftkings", "tier": "T1",
            "size": "1.00", "result": "W",
        })

    import results_graphic as rg
    importlib.reload(rg)
    monkeypatch.setattr(rg, "PICK_LOG_PATH", str(log))

    picks = rg._load_day_picks("2026-04-20")
    assert any(p["player"] == "Legacy Row" for p in picks), (
        "A row with blank run_type must still be emitted (defaults to "
        "'primary'). If this fails, a recent change dropped rows with "
        "missing run_type — verify CLAUDE.md schema + loader."
    )


def test_load_day_picks_rejects_manual_even_if_graded_w(tmp_path, monkeypatch):
    """Explicit: a graded winning manual pick (best-case temptation to leak)
    must still be filtered out. This catches a regression where someone
    'fixes' a filter to 'include all graded picks' and accidentally opens
    the manual-leak hole.
    """
    from pick_log_schema import CANONICAL_HEADER

    log = tmp_path / "pick_log.csv"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
        w.writeheader()
        for run_type, player in [
            ("primary", "Public Win"),
            ("manual",  "Manual Win"),
        ]:
            w.writerow({
                "date": "2026-04-20", "run_time": "10:00", "run_type": run_type,
                "sport": "NBA", "player": player, "team": "X",
                "stat": "PTS", "line": "20", "direction": "over",
                "odds": "-110", "book": "draftkings", "tier": "T1",
                "size": "1.00", "result": "W",
            })

    import results_graphic as rg
    importlib.reload(rg)
    monkeypatch.setattr(rg, "PICK_LOG_PATH", str(log))
    picks = rg._load_day_picks("2026-04-20")
    players = {p["player"] for p in picks}
    assert players == {"Public Win"}, (
        f"H-6: manual pick leaked into public graphic. players={players!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cross-module contract — H-5 and H-6 share a refund semantic
# ─────────────────────────────────────────────────────────────────────────────

def test_weekly_recap_and_results_graphic_agree_on_refund_semantics():
    """weekly_recap (H-5) and results_graphic both compute daily_stats.
    The refund set MUST match across both modules — otherwise a week's ROI
    in the xlsx recap won't match the daily graphic ROI and users will
    rightly lose trust in the numbers.
    """
    from weekly_recap import _REFUNDED_RESULTS as wr_set
    from results_graphic import _REFUNDED_RESULTS as rg_set
    assert wr_set == rg_set, (
        f"Refund sets drifted: weekly_recap={wr_set!r} "
        f"vs results_graphic={rg_set!r}. Unify or they'll report "
        "different ROIs for the same week."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fallback runner (no pytest required)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
