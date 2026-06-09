"""WNBA go-live (2026-06-09) — shadow removal, REB floor pin, KILLSHOT exclusion.

Locks in the go-live contract:
  - WNBA removed from SHADOW_SPORTS in run_picks.py AND grade_picks.py
  - SHADOW_LOG_PATHS empty (picks log to main pick_log.csv)
  - WNBA REB Kelly mult pinned to 0.10 both directions (35.3% shadow WR n=17;
    sizes land on the 0.25u floor — data keeps accumulating, money stays minimal)
  - WNBA explicitly excluded from KILLSHOT (pre-registered: TIER_FINDINGS.md /
    WNBA_RESEARCH_FINDINGS.md — was implicitly excluded by the shadow split)
  - Real gates (G_WNBA_EDGE, R4 REB-over shadow routing) remain ACTIVE
  - post_nrfi_bonus.py routes WNBA to the main log
"""

import sys
from pathlib import Path

import pytest

import run_picks
from run_picks import (
    SHADOW_SPORTS,
    SHADOW_LOG_PATHS,
    get_market_mult,
    size_picks_base,
    apply_hard_rules,
    check_prop_gates,
    _passes_killshot_v2_gate,
)


# ---------------------------------------------------------------------------
# Shadow removal
# ---------------------------------------------------------------------------

def test_wnba_not_in_run_picks_shadow_sports():
    assert "WNBA" not in SHADOW_SPORTS


def test_run_picks_shadow_sports_empty():
    """No shadow sports remain post-go-live. A new shadow sport must also add
    a SHADOW_LOG_PATHS entry — update this test deliberately when that happens."""
    assert SHADOW_SPORTS == set()


def test_shadow_log_paths_empty():
    assert SHADOW_LOG_PATHS == {}


def test_grade_picks_shadow_sports_empty():
    import grade_picks
    assert grade_picks.SHADOW_SPORTS == set()


# ---------------------------------------------------------------------------
# REB Kelly mult pinned to floor (both directions)
# ---------------------------------------------------------------------------

def test_wnba_reb_mult_under():
    assert get_market_mult("WNBA", "REB", "under") == 0.10


def test_wnba_reb_mult_over():
    """None-keyed entry covers over too (lookup falls through to (sport, stat, None))."""
    assert get_market_mult("WNBA", "REB", "over") == 0.10


def test_wnba_reb_under_pinned_to_floor():
    """Load-bearing regression: wp=0.65/-110 sized 0.50u under the old 0.25 mult
    (Kelly base ~1.59u x 0.25 = 0.40 -> rounds to 0.50). The 0.10 mult lands it
    on the 0.25u floor."""
    p = {"sport": "WNBA", "stat": "REB", "direction": "under",
         "win_prob": 0.65, "odds": -110, "tier": "T1"}
    assert size_picks_base([p])[0]["size"] == 0.25


def test_wnba_reb_floor_pin_strong_pick():
    """Even a strong REB pick stays at the floor."""
    p = {"sport": "WNBA", "stat": "REB", "direction": "under",
         "win_prob": 0.70, "odds": -105, "tier": "T1"}
    assert size_picks_base([p])[0]["size"] == 0.25


def test_wnba_pts_mult_unchanged():
    assert get_market_mult("WNBA", "PTS", "over") == 1.00
    assert get_market_mult("WNBA", "PTS", "under") == 1.00


def test_wnba_ast_over_mult_unchanged():
    assert get_market_mult("WNBA", "AST", "over") == 0.10


# ---------------------------------------------------------------------------
# KILLSHOT exclusion
# ---------------------------------------------------------------------------

def _killshot_pick(sport):
    """Pick that passes every v3 gate except (for WNBA) the sport exclusion."""
    return {
        "sport": sport, "player": "Test Player", "tier": "T2",
        "pick_score": 92.0, "win_prob": 0.72, "edge": 0.15,
        "odds": -130, "stat": "PTS", "line": 22.5, "direction": "over",
        "run_type": "primary",
    }


def test_wnba_killshot_excluded():
    ok, reason = _passes_killshot_v2_gate(_killshot_pick("WNBA"))
    assert not ok
    assert "WNBA" in reason


def test_nba_killshot_identical_pick_passes():
    """Same pick with sport=NBA passes — proves the WNBA check is the only blocker."""
    ok, reason = _passes_killshot_v2_gate(_killshot_pick("NBA"))
    assert ok, f"NBA twin should pass; got reason={reason}"


# ---------------------------------------------------------------------------
# Real gates stay active post-go-live
# ---------------------------------------------------------------------------

def test_wnba_reb_over_still_shadow_routed():
    """R4 REB-over shadow routing is sport-agnostic — WNBA REB overs keep
    accumulating data in pick_log_shadow_stats.csv, never go live."""
    shadow = []
    picks = [{"sport": "WNBA", "stat": "REB", "direction": "over", "line": 7.5}]
    result = apply_hard_rules(picks, shadow_dest=shadow)
    assert len(result) == 0
    assert len(shadow) == 1
    assert shadow[0]["gate_result"] == "R4_REB_OVER"


def test_wnba_edge_gate_still_active():
    """G_WNBA_EDGE (EV-per-unit floor 0.0955) survived go-live — it is a real
    gate, not a shadow artifact. EV = 0.58/0.5349 - 1 ~ 0.084 < 0.0955."""
    pick = {"stat": "PTS", "direction": "over", "line": 14.5, "proj": 19.0,
            "win_prob": 0.58, "adj_edge": 0.052, "odds": -115, "sport": "WNBA"}
    passed, gate = check_prop_gates(pick)
    assert not passed
    assert gate == "G_WNBA_EDGE"


# ---------------------------------------------------------------------------
# post_nrfi_bonus routing
# ---------------------------------------------------------------------------

def test_post_nrfi_routes_wnba_to_main_log():
    for modname in ("post_nrfi_bonus",):
        if modname in sys.modules:
            del sys.modules[modname]
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))
    try:
        import post_nrfi_bonus as pnb
    except Exception as e:  # pragma: no cover
        pytest.skip(f"Cannot import post_nrfi_bonus: {e}")
    finally:
        sys.path.remove(str(repo_root))

    assert pnb._log_path_for("WNBA") == pnb.MAIN_LOG
    assert pnb._SHADOW_SPORTS == frozenset()


# ---------------------------------------------------------------------------
# Recap aggregation includes WNBA
# ---------------------------------------------------------------------------

def _wnba_row(date, result):
    return {"date": date, "result": result, "run_type": "primary",
            "sport": "WNBA", "size": "0.25", "odds": "-110"}


def test_get_month_picks_includes_wnba():
    from grade_picks import get_month_picks
    rows = [_wnba_row("2026-06-09", "W"), _wnba_row("2026-06-10", "L")]
    picked = get_month_picks(rows, 2026, 6)
    assert len(picked) == 2


def test_pick_streak_includes_wnba():
    """compute_pick_streak no longer filters WNBA out (SHADOW_SPORTS empty)."""
    from grade_picks import compute_pick_streak
    rows = [_wnba_row("2026-06-07", "W"), _wnba_row("2026-06-08", "W"),
            _wnba_row("2026-06-09", "W")]
    count, direction = compute_pick_streak(rows)
    assert (count, direction) == (3, "W")
