"""test_killshot_v2.py — regression tests for KILLSHOT v2 qualification gate and sizing.

Locks the v2 spec:
  - Auto-qualify gate (ALL must pass):
      tier == "T1" strictly
      pick_score >= 90
      win_prob >= 0.65
      odds in [-200, +110]
      stat in {PTS, REB, AST, SOG, 3PM}
  - Sizing:
      3u default
      4u iff win_prob >= 0.70 AND edge >= 0.06
      capped at 4u (no 5u tier)
  - Weekly cap: 2 KILLSHOTs per rolling 7 days
  - Manual override (--killshot NAME): bypasses v2 gate, still counts toward cap,
    still requires score >= 75

Run:
    cd engine && python -m pytest ../test_killshot_v2.py -v

Pure-function tests. No network, no Discord, no filesystem (weekly-cap test patches _killshots_this_week).
"""

import sys
from pathlib import Path
from unittest.mock import patch

ENGINE_DIR = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import run_picks  # noqa: E402
from run_picks import (  # noqa: E402
    _killshot_size,
    _passes_killshot_v2_gate,
    select_killshots,
    KILLSHOT_SCORE_FLOOR,
    KILLSHOT_WIN_PROB_FLOOR,
    KILLSHOT_ODDS_MIN,
    KILLSHOT_ODDS_MAX,
    KILLSHOT_STAT_ALLOW,
    KILLSHOT_SIZE_BASE,
    KILLSHOT_SIZE_BUMP,
    KILLSHOT_BUMP_WIN_PROB,
    KILLSHOT_BUMP_EDGE,
    KILLSHOT_WEEKLY_CAP,
    KILLSHOT_MANUAL_FLOOR,
    KILLSHOT_TIER_REQUIRED,
)


def _pick(**overrides):
    """Build a pick that passes every v2 gate by default. Override individual fields to test each."""
    base = {
        "player": "Test Player",
        "tier": "T1",
        "pick_score": 92.0,
        "win_prob": 0.72,
        "edge": 0.15,
        "odds": -130,
        "stat": "PTS",
        "line": 25.5,
        "direction": "over",
        "run_type": "primary",
    }
    base.update(overrides)
    return base


# ─── v2 gate: passes ────────────────────────────────────────────────────────────

def test_gate_passes_on_clean_T1():
    ok, reason = _passes_killshot_v2_gate(_pick())
    assert ok, f"Clean T1 pick should pass; got reason={reason}"


def test_gate_passes_all_allowed_stats():
    for stat in ("PTS", "REB", "AST", "SOG", "3PM"):
        ok, reason = _passes_killshot_v2_gate(_pick(stat=stat))
        assert ok, f"stat={stat} should pass; got reason={reason}"


def test_gate_passes_at_odds_lower_boundary():
    ok, _ = _passes_killshot_v2_gate(_pick(odds=KILLSHOT_ODDS_MIN))
    assert ok, "odds == KILLSHOT_ODDS_MIN (-200) should pass (inclusive boundary)"


def test_gate_passes_at_odds_upper_boundary():
    ok, _ = _passes_killshot_v2_gate(_pick(odds=KILLSHOT_ODDS_MAX))
    assert ok, "odds == KILLSHOT_ODDS_MAX (+110) should pass (inclusive boundary)"


def test_gate_passes_at_win_prob_floor():
    ok, _ = _passes_killshot_v2_gate(_pick(win_prob=KILLSHOT_WIN_PROB_FLOOR))
    assert ok, "win_prob == floor (0.65) should pass (inclusive)"


def test_gate_passes_at_score_floor():
    ok, _ = _passes_killshot_v2_gate(_pick(pick_score=KILLSHOT_SCORE_FLOOR))
    assert ok, "pick_score == floor (90) should pass (inclusive)"


# ─── v2 gate: rejects ────────────────────────────────────────────────────────────

def test_gate_rejects_T1B():
    ok, reason = _passes_killshot_v2_gate(_pick(tier="T1B"))
    assert not ok
    assert "tier" in reason


def test_gate_rejects_T2():
    ok, reason = _passes_killshot_v2_gate(_pick(tier="T2"))
    assert not ok
    assert "tier" in reason


def test_gate_rejects_T3():
    ok, reason = _passes_killshot_v2_gate(_pick(tier="T3"))
    assert not ok
    assert "tier" in reason


def test_gate_rejects_score_below_floor():
    ok, reason = _passes_killshot_v2_gate(_pick(pick_score=89.9))
    assert not ok
    assert "score" in reason.lower()


def test_gate_rejects_win_prob_below_floor():
    ok, reason = _passes_killshot_v2_gate(_pick(win_prob=0.649))
    assert not ok
    assert "win_prob" in reason


def test_gate_rejects_odds_below_min():
    ok, reason = _passes_killshot_v2_gate(_pick(odds=-201))
    assert not ok
    assert "odds" in reason


def test_gate_rejects_odds_above_max():
    ok, reason = _passes_killshot_v2_gate(_pick(odds=120))
    assert not ok
    assert "odds" in reason


def test_gate_rejects_disallowed_stats():
    for stat in ("PARLAY", "TEAM_TOTAL", "ML_DOG", "F5_ML", "SPREAD", "ML_FAV", "TOTAL"):
        ok, reason = _passes_killshot_v2_gate(_pick(stat=stat))
        assert not ok, f"stat={stat} should be rejected under v2 allowlist"
        assert "stat" in reason


def test_gate_rejects_missing_tier():
    ok, reason = _passes_killshot_v2_gate(_pick(tier=""))
    assert not ok
    assert "tier" in reason


# ─── sizing ─────────────────────────────────────────────────────────────────────

def test_size_default_is_3u():
    # Low edge, bump shouldn't fire even with high wp
    size = _killshot_size(_pick(win_prob=0.75, edge=0.05))
    assert size == KILLSHOT_SIZE_BASE == 3.0


def test_size_bumps_to_4u_when_both_thresholds_met():
    size = _killshot_size(_pick(win_prob=KILLSHOT_BUMP_WIN_PROB, edge=KILLSHOT_BUMP_EDGE))
    assert size == KILLSHOT_SIZE_BUMP == 4.0


def test_size_stays_3u_when_only_win_prob_meets_bump():
    size = _killshot_size(_pick(win_prob=0.75, edge=0.05))
    assert size == 3.0, "high wp alone should not trigger bump"


def test_size_stays_3u_when_only_edge_meets_bump():
    size = _killshot_size(_pick(win_prob=0.68, edge=0.10))
    assert size == 3.0, "high edge alone (with wp<0.70) should not trigger bump"


def test_size_no_5u_tier_even_at_extreme_values():
    # v2 explicitly caps at 4u — no 5u even with huge wp/edge
    size = _killshot_size(_pick(win_prob=0.95, edge=0.50))
    assert size == 4.0, "size should cap at 4u (no 5u tier in v2)"


def test_size_handles_missing_fields_gracefully():
    # Defensive: if pick is missing fields, fall back to base size (never crash)
    size = _killshot_size({"player": "x"})
    assert size == 3.0


def test_size_handles_non_numeric_fields():
    size = _killshot_size({"win_prob": "n/a", "edge": "n/a"})
    assert size == 3.0


def test_size_reads_adj_edge_when_edge_absent():
    """Production regression: internal pick dicts use adj_edge, not edge.
    Was silently defaulting edge to 0 and never bumping (LaRavia 2026-04-21).
    """
    pick = {"win_prob": 0.73, "adj_edge": 0.18}   # no 'edge' key at all
    assert _killshot_size(pick) == 4.0


def test_size_prefers_adj_edge_over_edge_when_both_present():
    """If both keys exist, adj_edge wins (it's the canonical internal key)."""
    pick = {"win_prob": 0.73, "adj_edge": 0.18, "edge": 0.01}
    assert _killshot_size(pick) == 4.0


def test_size_falls_back_to_edge_when_adj_edge_absent():
    """Rows reconstructed from pick_log.csv carry 'edge' only - must still work."""
    pick = {"win_prob": 0.73, "edge": 0.18}   # no 'adj_edge'
    assert _killshot_size(pick) == 4.0


# ─── select_killshots integration ────────────────────────────────────────────────

def test_select_includes_clean_T1_pick():
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick()]
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == 1
    assert ks[0]["tier"] == "KILLSHOT"
    assert ks[0]["size"] == 4.0  # passes bump (wp=0.72, edge=0.15)


def test_select_excludes_T1B_even_with_score_above_90():
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(tier="T1B", pick_score=95.0)]
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == 0, "T1B picks must NOT auto-qualify under v2 (T1 strict)"


def test_select_excludes_disallowed_stat():
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(stat="TEAM_TOTAL")]
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == 0


def test_select_respects_weekly_cap_of_2():
    picks = [
        _pick(player="A", pick_score=92.0),
        _pick(player="B", pick_score=91.0),
        _pick(player="C", pick_score=90.5),  # should be cut by cap
    ]
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == KILLSHOT_WEEKLY_CAP == 2, "weekly cap should limit to 2"


def test_select_empty_when_cap_already_reached():
    picks = [_pick()]
    with patch.object(run_picks, "_killshots_this_week", return_value=KILLSHOT_WEEKLY_CAP):
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == 0


def test_select_remaining_cap_limits_qualifiers():
    # 1 already posted this week, 2 candidates → only 1 passes
    picks = [
        _pick(player="A", pick_score=92.0),
        _pick(player="B", pick_score=91.0),
    ]
    with patch.object(run_picks, "_killshots_this_week", return_value=1):
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == 1
    assert ks[0]["player"] == "A", "highest score should win the remaining cap slot"


def test_select_sorts_by_score_desc():
    picks = [
        _pick(player="Low",  pick_score=91.0),
        _pick(player="High", pick_score=95.0),
        _pick(player="Mid",  pick_score=92.0),
    ]
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        ks = select_killshots(picks, "2026-04-21")
    # Cap is 2, so High + Mid make it; Low is cut
    assert [p["player"] for p in ks] == ["High", "Mid"]


# ─── manual override ────────────────────────────────────────────────────────────

def test_manual_override_bypasses_v2_filters():
    # T2 pick (would fail v2 gate) with score=80 (below auto floor) — manual promote should work
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="Doncic Luka", tier="T2", pick_score=80.0, win_prob=0.58, odds=150, stat="PARLAY")]
        ks = select_killshots(picks, "2026-04-21", manual_players={"Doncic"})
    assert len(ks) == 1, "manual override should bypass tier/wp/odds/stat gates"
    assert ks[0]["tier"] == "KILLSHOT"


def test_manual_override_still_requires_manual_floor():
    # Score below manual floor (75) — should NOT promote even with name match
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="Doncic Luka", pick_score=KILLSHOT_MANUAL_FLOOR - 0.1)]
        ks = select_killshots(picks, "2026-04-21", manual_players={"Doncic"})
    assert len(ks) == 0, "manual promote should still require score >= MANUAL_FLOOR (75)"


def test_manual_override_counts_toward_weekly_cap():
    # 1 already posted, 2 manual candidates → only 1 passes
    picks = [
        _pick(player="Pastrnak David", tier="T2", pick_score=78.0),
        _pick(player="McDavid Connor", tier="T2", pick_score=77.0),
    ]
    with patch.object(run_picks, "_killshots_this_week", return_value=1):
        ks = select_killshots(picks, "2026-04-21", manual_players={"Pastrnak", "McDavid"})
    assert len(ks) == 1, "manual promotes must respect remaining weekly cap"


def test_manual_player_match_case_insensitive():
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="McDavid Connor", tier="T2", pick_score=80.0)]
        ks = select_killshots(picks, "2026-04-21", manual_players={"mcdavid"})
    assert len(ks) == 1


# ─── constants sanity ───────────────────────────────────────────────────────────

def test_constants_are_sane():
    assert KILLSHOT_TIER_REQUIRED == "T1"
    assert KILLSHOT_WEEKLY_CAP == 2
    assert KILLSHOT_SCORE_FLOOR == 90.0
    assert KILLSHOT_WIN_PROB_FLOOR == 0.65
    assert KILLSHOT_ODDS_MIN == -200
    assert KILLSHOT_ODDS_MAX == 110
    assert KILLSHOT_STAT_ALLOW == frozenset({"PTS", "REB", "AST", "SOG", "3PM"})
    assert KILLSHOT_SIZE_BASE == 3.0
    assert KILLSHOT_SIZE_BUMP == 4.0
    assert KILLSHOT_BUMP_WIN_PROB == 0.70
    assert KILLSHOT_BUMP_EDGE == 0.06


if __name__ == "__main__":
    # Allow `python test_killshot_v2.py` without pytest
    import inspect
    failures = []
    tests = [(n, fn) for n, fn in globals().items() if n.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            failures.append((name, e))
            print(f"  FAIL  {name}: {e}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
