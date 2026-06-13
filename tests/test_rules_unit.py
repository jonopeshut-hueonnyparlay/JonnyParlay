"""Tests for rules.py functions not covered elsewhere.

apply_hard_rules (R4/R11) is covered by tests/test_hard_rules.py; apply_caps by
tests/test_no_cap_bypasses_apply_caps.py; the R8-retirement behavior of
apply_soft_rules_premium by tests/test_plan9_tier_restructure.py. Filled here:
auto_r12_from_log (disk read), apply_r12_cooldown, and the R6/R10 soft-rule
trimming of apply_soft_rules_premium.
"""
import csv
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

import rules
from rules import auto_r12_from_log, apply_r12_cooldown, apply_soft_rules_premium
from thresholds import MAX_PREMIUM_PICKS


# ---------------------------------------------------------------------------
# auto_r12_from_log — reads PICK_LOG_PATH from disk
# ---------------------------------------------------------------------------

def _write_log(path, rows):
    fields = ["date", "result", "run_type", "player"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_auto_r12_returns_recent_losers_only(tmp_path):
    log = tmp_path / "pick_log.csv"
    _write_log(log, [
        {"date": "2026-06-11", "result": "L", "run_type": "primary", "player": "Recent Loser"},
        {"date": "2026-06-11", "result": "W", "run_type": "primary", "player": "Recent Winner"},
        {"date": "2026-06-11", "result": "L", "run_type": "manual", "player": "Manual Loser"},
        {"date": "2026-06-01", "result": "L", "run_type": "primary", "player": "Old Loser"},
        {"date": "2026-06-13", "result": "L", "run_type": "primary", "player": "Today Loser"},
    ])
    with mock.patch.object(rules, "PICK_LOG_PATH", str(log)):
        losers = auto_r12_from_log("2026-06-13", window_days=5)
    assert isinstance(losers, list)
    assert "Recent Loser" in losers
    assert "Recent Winner" not in losers   # won
    assert "Manual Loser" not in losers     # run_type=manual excluded
    assert "Old Loser" not in losers        # outside 5-day window
    assert "Today Loser" not in losers      # today not graded yet


def test_auto_r12_missing_log_returns_empty(tmp_path):
    missing = tmp_path / "nope.csv"
    with mock.patch.object(rules, "PICK_LOG_PATH", str(missing)):
        assert auto_r12_from_log("2026-06-13") == []


# ---------------------------------------------------------------------------
# apply_r12_cooldown
# ---------------------------------------------------------------------------

def test_apply_r12_cooldown_removes_matching():
    picks = [{"player": "LeBron James", "stat": "PTS"},
             {"player": "Nikola Jokic", "stat": "AST"}]
    out = apply_r12_cooldown(picks, ["LeBron James"])
    names = {p["player"] for p in out}
    assert "LeBron James" not in names
    assert "Nikola Jokic" in names


def test_apply_r12_cooldown_passthrough_non_matching():
    picks = [{"player": "Stephen Curry", "stat": "3PM"}]
    out = apply_r12_cooldown(picks, ["Some Other Player"])
    assert len(out) == 1


def test_apply_r12_cooldown_empty_is_noop():
    picks = [{"player": "A", "stat": "PTS"}, {"player": "B", "stat": "AST"}]
    assert apply_r12_cooldown(picks, []) == picks


# ---------------------------------------------------------------------------
# apply_soft_rules_premium — R6 (max 2 overs) / R10 (max 1 per stat)
# ---------------------------------------------------------------------------

def _pick(player, stat, game, score, direction="under", win_prob=0.62):
    return {
        "player": player, "stat": stat, "game": game, "pick_score": score,
        "direction": direction, "win_prob": win_prob, "sport": "NBA", "odds": -110,
    }


def test_soft_rules_clean_set_fills_by_score():
    qualifying = [
        _pick("A", "PTS", "G1 @ H1", 90),
        _pick("B", "AST", "G2 @ H2", 80),
        _pick("C", "OUTS", "G3 @ H3", 70),
        _pick("D", "HITS", "G4 @ H4", 60),
    ]
    premium = apply_soft_rules_premium([], qualifying)
    chosen = {p["player"] for p in premium}
    assert len(premium) == MAX_PREMIUM_PICKS
    assert chosen == {"A", "B", "C"}   # top 3 by pick_score; D displaced


def test_soft_rules_r10_one_per_stat():
    qualifying = [
        _pick("A", "PTS", "G1 @ H1", 90),
        _pick("B", "PTS", "G2 @ H2", 80),
        _pick("C", "PTS", "G3 @ H3", 70),
    ]
    premium = apply_soft_rules_premium([], qualifying)
    assert len(premium) == 1   # R10: max 1 pick per stat


def test_soft_rules_r6_max_two_overs():
    qualifying = [
        _pick("A", "PTS", "G1 @ H1", 90, direction="over"),
        _pick("B", "AST", "G2 @ H2", 80, direction="over"),
        _pick("C", "OUTS", "G3 @ H3", 70, direction="over"),
        _pick("D", "HITS", "G4 @ H4", 60, direction="over"),
    ]
    premium = apply_soft_rules_premium([], qualifying)
    assert len(premium) == 2   # R6: max 2 overs on a 3-pick card
    assert all(p["direction"] == "over" for p in premium)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
