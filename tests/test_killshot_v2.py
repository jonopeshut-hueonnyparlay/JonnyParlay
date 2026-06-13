"""test_killshot_v2.py — regression tests for the KILLSHOT qualification gate and sizing.

Locks the v3 spec (Plan 6 §13 redesign, 2026-06-05):
  - Auto-qualify gate (ALL must pass — NO tier requirement in v3):
      pick_score >= 65
      odds in [-200, +110]
      win_prob >= implied_prob(odds) + KILLSHOT_WP_MARGIN (0.03)  # odds-dependent
      stat in {PTS, AST}   # SOG removed while G_SOG_SUSPENDED; REB dropped (L9)
  - Sizing:
      3u default
      4u iff win_prob >= 0.70 AND edge >= 0.06
      capped at 4u (no 5u tier)
  - Weekly cap: 2 KILLSHOTs per rolling 7 days
  - Manual override (--killshot NAME): bypasses score/stat selection, still requires
    score >= 75 AND the odds range AND the odds-dependent wp floor (v2's manual
    path was score-only — a latent −EV bypass), counts toward cap
  - Module-load invariant: every allowlisted stat is unsuspended + tier-eligible

Run:
    python -m pytest tests/test_killshot_v2.py -v

Pure-function tests. No network, no Discord; blocked-pick logging is redirected
to tmp_path (near-miss disqualifications write to pick_log_blocked.csv).
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1] / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

import run_picks  # noqa: E402
from run_picks import (  # noqa: E402
    _assert_killshot_invariants,
    _killshot_odds_wp_ok,
    _killshot_size,
    _passes_killshot_v2_gate,
    implied_prob,
    select_killshots,
    KILLSHOT_SCORE_FLOOR,
    KILLSHOT_WP_MARGIN,
    KILLSHOT_ODDS_MIN,
    KILLSHOT_ODDS_MAX,
    KILLSHOT_STAT_ALLOW,
    KILLSHOT_SIZE_BASE,
    KILLSHOT_SIZE_BUMP,
    KILLSHOT_BUMP_WIN_PROB,
    KILLSHOT_BUMP_EDGE,
    KILLSHOT_WEEKLY_CAP,
    KILLSHOT_MANUAL_FLOOR,
    SUSPENDED_STATS,
)


@pytest.fixture(autouse=True)
def _patch_blocked_log(tmp_path, monkeypatch):
    """Near-miss disqualifications append to pick_log_blocked.csv — redirect."""
    # log_blocked_pick now lives in pick_log_writers (Phase 2a Step 7); patch the path
    # it reads there AND the run_picks re-export some tests assert against.
    import pick_log_writers
    blocked = str(tmp_path / "pick_log_blocked.csv")
    monkeypatch.setattr(pick_log_writers, "PICK_LOG_BLOCKED_PATH", blocked)
    monkeypatch.setattr(run_picks, "PICK_LOG_BLOCKED_PATH", blocked)


def _pick(**overrides):
    """Build a pick that passes every v3 gate by default. Override fields to test each.
    At odds=-130 the odds-dependent wp floor is implied_prob(-130)+0.03 ≈ 0.595."""
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


# ─── v3 gate: passes ────────────────────────────────────────────────────────────

def test_gate_passes_on_clean_pick():
    ok, reason = _passes_killshot_v2_gate(_pick())
    assert ok, f"Clean pick should pass; got reason={reason}"


def test_gate_passes_all_allowed_stats():
    for stat in sorted(KILLSHOT_STAT_ALLOW):
        ok, reason = _passes_killshot_v2_gate(_pick(stat=stat))
        assert ok, f"stat={stat} should pass; got reason={reason}"


def test_gate_passes_at_odds_lower_boundary():
    # At -200 the wp floor is implied_prob(-200)+0.03 ≈ 0.697 — needs high wp
    ok, _ = _passes_killshot_v2_gate(_pick(odds=KILLSHOT_ODDS_MIN, win_prob=0.70))
    assert ok, "odds == KILLSHOT_ODDS_MIN (-200) should pass (inclusive boundary)"


def test_gate_passes_at_odds_upper_boundary():
    ok, _ = _passes_killshot_v2_gate(_pick(odds=KILLSHOT_ODDS_MAX))
    assert ok, "odds == KILLSHOT_ODDS_MAX (+110) should pass (inclusive boundary)"


def test_gate_passes_at_exact_wp_floor():
    floor = implied_prob(-130) + KILLSHOT_WP_MARGIN
    ok, _ = _passes_killshot_v2_gate(_pick(win_prob=floor))
    assert ok, "win_prob == breakeven+margin should pass (inclusive)"


def test_gate_passes_at_score_floor():
    ok, _ = _passes_killshot_v2_gate(_pick(pick_score=KILLSHOT_SCORE_FLOOR))
    assert ok, "pick_score == floor (65) should pass (inclusive)"


# ─── v3: tier requirement dropped ────────────────────────────────────────────────

def test_gate_accepts_any_tier():
    """v3 dropped the T1-strict requirement: PTS is T2, so PTS ∧ tier=T1 was
    logically unsatisfiable — the gate was dead for 5+ weeks. T1 WR (46.6%)
    < T2 (60.3%); selection on floors is strictly better."""
    for tier in ("T1", "T1B", "T2", "T3", ""):
        ok, reason = _passes_killshot_v2_gate(_pick(tier=tier))
        assert ok, f"tier={tier!r} should not matter in v3; got reason={reason}"


# ─── v3 gate: rejects ────────────────────────────────────────────────────────────

def test_gate_rejects_score_below_floor():
    ok, reason = _passes_killshot_v2_gate(_pick(pick_score=64.9))
    assert not ok
    assert "score" in reason.lower()


def test_gate_rejects_win_prob_below_odds_dependent_floor():
    # At -130 the floor is ≈0.595
    ok, reason = _passes_killshot_v2_gate(_pick(win_prob=0.59))
    assert not ok
    assert "win_prob" in reason


def test_gate_closes_latent_ev_window_at_minus_200():
    """The v2 static floor (0.65) was −EV at −200 (breakeven 0.667).
    v3's odds-dependent floor (0.697 at −200) closes the window."""
    ok, reason = _passes_killshot_v2_gate(_pick(odds=-200, win_prob=0.66))
    assert not ok, "wp=0.66 at -200 is -EV and must be rejected in v3"
    assert "win_prob" in reason


def test_gate_wp_floor_scales_with_odds():
    """Same wp can pass at light juice and fail at heavy juice."""
    ok_light, _ = _passes_killshot_v2_gate(_pick(odds=-110, win_prob=0.62))
    ok_heavy, _ = _passes_killshot_v2_gate(_pick(odds=-180, win_prob=0.62))
    assert ok_light, "wp=0.62 at -110 (floor ≈0.554) should pass"
    assert not ok_heavy, "wp=0.62 at -180 (floor ≈0.673) should fail"


def test_gate_rejects_odds_below_min():
    ok, reason = _passes_killshot_v2_gate(_pick(odds=-201, win_prob=0.75))
    assert not ok
    assert "odds" in reason


def test_gate_rejects_odds_above_max():
    ok, reason = _passes_killshot_v2_gate(_pick(odds=120))
    assert not ok
    assert "odds" in reason


def test_gate_rejects_disallowed_stats():
    for stat in ("SOG", "PARLAY", "TEAM_TOTAL", "ML_DOG", "F5_ML", "SPREAD", "ML_FAV", "TOTAL"):
        ok, reason = _passes_killshot_v2_gate(_pick(stat=stat))
        assert not ok, f"stat={stat} should be rejected under v3 allowlist"
        assert "stat" in reason


def test_gate_rejects_suspended_sog():
    """SOG removed from the allowlist while G_SOG_SUSPENDED is active — re-add
    at the July refit when the suspension lifts."""
    ok, reason = _passes_killshot_v2_gate(_pick(stat="SOG"))
    assert not ok
    assert "stat" in reason


# ─── module-load invariant (8b) ──────────────────────────────────────────────────

def test_invariant_passes_on_current_config():
    _assert_killshot_invariants()   # must not raise


def test_invariant_rejects_suspended_stat_in_allowlist(monkeypatch):
    monkeypatch.setattr(run_picks, "KILLSHOT_STAT_ALLOW", frozenset({"PTS", "SOG"}))
    with pytest.raises(AssertionError, match="suspended"):
        run_picks._assert_killshot_invariants()


def test_invariant_rejects_tier_orphan_stat(monkeypatch):
    monkeypatch.setattr(run_picks, "KILLSHOT_STAT_ALLOW", frozenset({"PTS", "NOT_A_STAT"}))
    with pytest.raises(AssertionError, match="tier"):
        run_picks._assert_killshot_invariants()


def test_allowlist_has_no_suspended_stats():
    assert not (KILLSHOT_STAT_ALLOW & set(SUSPENDED_STATS))


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
    # Explicitly caps at 4u — no 5u even with huge wp/edge
    size = _killshot_size(_pick(win_prob=0.95, edge=0.50))
    assert size == 4.0, "size should cap at 4u (no 5u tier)"


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

def test_select_includes_clean_pick():
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick()]
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == 1
    assert ks[0]["tier"] == "KILLSHOT"
    assert ks[0]["size"] == 4.0  # passes bump (wp=0.72, edge=0.15)


def test_select_includes_T1B_and_T2_in_v3():
    """v2 excluded everything but strict T1 — v3 selects on floors only."""
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="A", tier="T1B", pick_score=95.0),
                 _pick(player="B", tier="T2", pick_score=94.0)]
        ks = select_killshots(picks, "2026-04-21")
    assert len(ks) == 2


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


# ─── 8d: near-miss logging ──────────────────────────────────────────────────────

def test_near_miss_logged_to_blocked_csv(tmp_path):
    """Picks meeting the score floor but failing another check are appended to
    pick_log_blocked.csv as KILLSHOT_{code} — v2's dead gate was console-only."""
    import csv
    blocked = Path(run_picks.PICK_LOG_BLOCKED_PATH)
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        select_killshots([_pick(stat="TEAM_TOTAL")], "2026-04-21")   # near-miss: STAT
        select_killshots([_pick(odds=-250, win_prob=0.80)], "2026-04-21")  # near-miss: ODDS
    assert blocked.exists()
    rows = list(csv.DictReader(open(blocked)))
    gates = {r["gate_result"] for r in rows}
    assert "KILLSHOT_STAT" in gates
    assert "KILLSHOT_ODDS" in gates


def test_low_score_disqualification_not_logged():
    """Score-floor failures are not near-misses — they must NOT flood the log."""
    blocked = Path(run_picks.PICK_LOG_BLOCKED_PATH)
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        select_killshots([_pick(pick_score=40.0)], "2026-04-21")
    assert not blocked.exists()


# ─── manual override (v3: odds/wp now enforced) ─────────────────────────────────

def test_manual_override_bypasses_score_and_stat_selection():
    # T2 PARLAY with score=80 (below auto behavior for stat) — manual promote works
    # as long as odds/wp pass: -130 with wp=0.62 (floor ≈0.595).
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="Doncic Luka", tier="T2", pick_score=80.0,
                       win_prob=0.62, odds=-130, stat="PARLAY")]
        ks = select_killshots(picks, "2026-04-21", manual_players={"Doncic"})
    assert len(ks) == 1, "manual override should bypass stat allowlist"
    assert ks[0]["tier"] == "KILLSHOT"


def test_manual_override_still_requires_manual_floor():
    # Score below manual floor (75) — should NOT promote even with name match.
    # stat=PARLAY keeps the auto path closed so only the manual path is in play
    # (in v3 a T2 PTS pick at score 74.9 would auto-qualify on floors alone).
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="Doncic Luka", tier="T2", stat="PARLAY",
                       pick_score=KILLSHOT_MANUAL_FLOOR - 0.1)]
        ks = select_killshots(picks, "2026-04-21", manual_players={"Doncic"})
    assert len(ks) == 0, "manual promote should still require score >= MANUAL_FLOOR (75)"


def test_manual_override_enforces_odds_range_in_v3():
    """v2's manual path bypassed odds entirely — a +150 dog could be promoted.
    v3 enforces the odds range on manual promotes."""
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="Doncic Luka", pick_score=90.0, odds=150, win_prob=0.58)]
        ks = select_killshots(picks, "2026-04-21", manual_players={"Doncic"})
    assert len(ks) == 0, "manual promote must respect the odds range in v3"


def test_manual_override_enforces_wp_floor_in_v3():
    """v2's manual path bypassed the wp floor — a −EV promote was possible.
    v3 enforces wp >= breakeven + margin on manual promotes."""
    with patch.object(run_picks, "_killshots_this_week", return_value=0):
        picks = [_pick(player="Doncic Luka", pick_score=90.0, odds=-200, win_prob=0.66)]
        ks = select_killshots(picks, "2026-04-21", manual_players={"Doncic"})
    assert len(ks) == 0, "manual promote at -200 with wp=0.66 is -EV and must be rejected"


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
    assert not hasattr(run_picks, "KILLSHOT_TIER_REQUIRED"), "v3 removed the tier requirement"
    assert not hasattr(run_picks, "KILLSHOT_WIN_PROB_FLOOR"), "v3 replaced the static wp floor"
    assert KILLSHOT_WEEKLY_CAP == 2
    assert KILLSHOT_SCORE_FLOOR == 65.0
    assert KILLSHOT_WP_MARGIN == 0.03
    assert KILLSHOT_ODDS_MIN == -200
    assert KILLSHOT_ODDS_MAX == 110
    assert KILLSHOT_STAT_ALLOW == frozenset({"PTS", "AST"})
    assert KILLSHOT_SIZE_BASE == 3.0
    assert KILLSHOT_SIZE_BUMP == 4.0
    assert KILLSHOT_BUMP_WIN_PROB == 0.70
    assert KILLSHOT_BUMP_EDGE == 0.06


def test_odds_wp_helper_codes():
    ok, _, code = _killshot_odds_wp_ok({"odds": -250, "win_prob": 0.80})
    assert (ok, code) == (False, "ODDS")
    ok, _, code = _killshot_odds_wp_ok({"odds": -130, "win_prob": 0.50})
    assert (ok, code) == (False, "WP")
    ok, reason, code = _killshot_odds_wp_ok({"odds": -130, "win_prob": 0.65})
    assert (ok, reason, code) == (True, "", "")


# ── H30: edge=None / adj_edge=None must not crash _killshot_size ─────────────

def test_size_none_adj_edge_returns_base():
    """_killshot_size falls back to KILLSHOT_SIZE_BASE when adj_edge is None."""
    pick = {
        "win_prob": 0.75, "adj_edge": None,
        "tier": "KILLSHOT", "stat": "PTS", "pick_score": 92.0,
        "odds": -130, "line": 25.5, "direction": "over",
    }
    assert _killshot_size(pick) == KILLSHOT_SIZE_BASE


def test_size_missing_edge_returns_base():
    """_killshot_size falls back to KILLSHOT_SIZE_BASE when adj_edge key absent."""
    pick = {
        "win_prob": 0.80,
        "tier": "KILLSHOT", "stat": "AST", "pick_score": 95.0,
        "odds": -110, "line": 9.5, "direction": "over",
    }
    assert _killshot_size(pick) == KILLSHOT_SIZE_BASE


def test_gate_none_edge_pick_is_not_crashed():
    """_passes_killshot_v2_gate does not reference edge — None edge must not cause
    an exception (gate checks score/odds/wp/stat)."""
    pick = {
        "tier": "T1", "pick_score": 92.0, "win_prob": 0.67,
        "odds": -130, "stat": "PTS", "adj_edge": None,
        "line": 25.5, "direction": "over",
    }
    passed, reason = _passes_killshot_v2_gate(pick)
    assert isinstance(passed, bool)   # must not raise
