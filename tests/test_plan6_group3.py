"""Plan 6 Group 3 regression tests (2026-06-05).

Covers:
  - Item 7:  R13 retired — no stacked pitcher corr_m in size_picks_vake()
  - Item 9a: G_WNBA_EDGE is an EV-per-unit floor (WNBA_EV_FLOOR=0.0955)
  - Item 9b: WNBA early-season dampener = sigma inflation / NB prob shrink
  - Item 9c: _wnba_team_games_played() helper + fallback semantics
  - Item 11: PICK_SCORE e_n hard cap at the 15% edge ceiling
"""

import datetime

import pytest

import run_picks
import prob_core
from run_picks import (
    _wnba_early_season_factor,
    _wnba_team_games_played,
    calc_prop_prob,
    check_prop_gates,
    implied_prob,
    pick_score,
    size_picks_vake,
    WNBA_EV_FLOOR,
    WNBA_SEASON_START,
)


# ---------------------------------------------------------------------------
# Item 7 — R13 retired
# ---------------------------------------------------------------------------

def _premium_pick(player, stat, game):
    return {
        "player": player, "stat": stat, "game": game, "tier": "T2",
        "win_prob": 0.62, "odds": -115, "pick_score": 80.0,
        "direction": "over", "sport": "MLB", "adj_edge": 0.07,
    }


def test_r13_retired_no_stacked_pitcher_penalty():
    """Two pitcher props in the same game (different pitchers — G11 guarantees
    that) get the GENERAL game corr_m (0.85), not an extra ×0.70 stack."""
    picks = [
        _premium_pick("Pitcher A", "OUTS", "NYY @ BOS"),
        _premium_pick("Pitcher B", "OUTS", "NYY @ BOS"),
    ]
    sized = size_picks_vake(picks)
    corr_second = sized[1]["size_detail"]["corr"]
    assert corr_second == pytest.approx(0.85), (
        f"second same-game pitcher prop should carry corr_m=0.85 (general game "
        f"correlation only); got {corr_second} — R13 stacking has been retired"
    )


# ---------------------------------------------------------------------------
# Item 9b — early-season factor + sigma inflation / NB shrink
# ---------------------------------------------------------------------------

def test_early_season_factor_schedule():
    d = WNBA_SEASON_START
    day = lambda n: d + datetime.timedelta(days=n - 1)
    assert _wnba_early_season_factor(day(5)) == 0.80    # days 1-14
    assert _wnba_early_season_factor(day(14)) == 0.80
    assert _wnba_early_season_factor(day(15)) == 0.90   # days 15-21
    assert _wnba_early_season_factor(day(21)) == 0.90
    assert _wnba_early_season_factor(day(22)) == 1.00   # day 22+
    assert _wnba_early_season_factor(day(0)) == 1.00    # pre-season


def test_wnba_normal_sigma_inflated_early_season(monkeypatch):
    """Early-season WNBA PTS probability must sit closer to 1/2 than late-season
    (sigma /= 0.80 widens the distribution)."""
    over_late, _ = calc_prop_prob(18.0, 14.5, "PTS", sport="WNBA")
    # calc_prop_prob now lives in prob_core (Phase 2a Step 5); patch the factor there.
    monkeypatch.setattr(prob_core, "_wnba_early_season_factor", lambda today=None: 0.80)
    over_early, _ = calc_prop_prob(18.0, 14.5, "PTS", sport="WNBA")
    assert over_late > 0.5
    assert 0.5 < over_early < over_late, (
        "early-season sigma inflation must shrink over_p toward 0.5")


def test_wnba_nb_prob_shrunk_early_season(monkeypatch):
    """WNBA NB-routed stats (AST/REB/3PM) have no sigma — the probability is
    shrunk toward 1/2 by the same factor."""
    over_late, under_late = calc_prop_prob(5.0, 3.5, "AST", sport="WNBA")
    # calc_prop_prob now lives in prob_core (Phase 2a Step 5); patch the factor there.
    monkeypatch.setattr(prob_core, "_wnba_early_season_factor", lambda today=None: 0.80)
    over_early, under_early = calc_prop_prob(5.0, 3.5, "AST", sport="WNBA")
    assert over_early == pytest.approx(0.5 + (over_late - 0.5) * 0.80)
    assert over_early + under_early == pytest.approx(1.0)


def test_nba_unaffected_by_wnba_dampener(monkeypatch):
    """The dampener is WNBA-only — NBA probabilities must not move."""
    before = calc_prop_prob(25.0, 22.5, "PTS", sport="NBA")
    # calc_prop_prob now lives in prob_core (Phase 2a Step 5); patch the factor there.
    monkeypatch.setattr(prob_core, "_wnba_early_season_factor", lambda today=None: 0.80)
    after = calc_prop_prob(25.0, 22.5, "PTS", sport="NBA")
    assert before == after


# ---------------------------------------------------------------------------
# Item 9a — G_WNBA_EDGE EV-per-unit floor
# ---------------------------------------------------------------------------

def _wnba_pick(win_prob, odds, adj_edge):
    return {
        "stat": "PTS", "direction": "over", "line": 14.5, "proj": 19.0,
        "win_prob": win_prob, "adj_edge": adj_edge, "odds": odds,
        "sport": "WNBA",
    }


def test_wnba_ev_floor_blocks_low_ev():
    # EV = wp/implied − 1 = 0.58/0.5349 − 1 ≈ 0.084 < 0.0955 → blocked
    passed, gate = check_prop_gates(_wnba_pick(win_prob=0.58, odds=-115, adj_edge=0.052))
    assert not passed
    assert gate == "G_WNBA_EDGE"


def test_wnba_ev_floor_passes_high_ev():
    # EV = 0.60/0.5349 − 1 ≈ 0.122 > 0.0955 → G_WNBA_EDGE passes
    passed, gate = check_prop_gates(_wnba_pick(win_prob=0.60, odds=-115, adj_edge=0.065))
    assert passed or gate != "G_WNBA_EDGE", f"unexpected gate: {gate}"


def test_wnba_ev_floor_no_longer_dead_code():
    """The old WNBA_EDGE_FLOOR=0.035 was always dominated by G9=0.05 (dead code).
    The EV floor binds at wider-than-(−110) vig even when raw edge clears G9:
    edge=0.051 at −120 → EV ≈ 0.0935 < 0.0955 → G_WNBA_EDGE fires where G9 wouldn't."""
    wp = implied_prob(-120) + 0.051   # edge 5.1% > G9's 5%
    ev = wp / implied_prob(-120) - 1.0
    assert ev < WNBA_EV_FLOOR
    passed, gate = check_prop_gates(_wnba_pick(win_prob=wp, odds=-120, adj_edge=0.051))
    assert not passed
    assert gate == "G_WNBA_EDGE"


def test_wnba_edge_floor_constant_removed():
    assert not hasattr(run_picks, "WNBA_EDGE_FLOOR")
    assert WNBA_EV_FLOOR == pytest.approx(0.0955)


# ---------------------------------------------------------------------------
# Item 9c — games-played opening gate helper
# ---------------------------------------------------------------------------

def test_games_played_unknown_team_returns_none():
    assert _wnba_team_games_played("Springfield Isotopes") is None


def test_games_played_missing_db_returns_none(monkeypatch):
    # _wnba_team_games_played now lives in wnba_gate (Phase 2a Step 3); patch the
    # DB path it actually reads. The cache is the same dict object via re-export.
    import wnba_gate
    monkeypatch.setattr(wnba_gate, "EDGEMODEL_DB_PATH", r"C:\nonexistent\nope.db")
    run_picks._WNBA_GP_CACHE.clear()
    assert _wnba_team_games_played("Las Vegas Aces") is None
    run_picks._WNBA_GP_CACHE.clear()


def test_games_played_live_db_counts():
    """With the real EdgeModel DB present, 2026-season counts are positive ints
    by June. Skip silently if the DB is unavailable in this environment."""
    gp = _wnba_team_games_played("Las Vegas Aces",
                                 today=datetime.date(2026, 6, 5))
    if gp is None:
        pytest.skip("EdgeModel DB not available")
    assert isinstance(gp, int) and gp >= 2


# ---------------------------------------------------------------------------
# Item 11 — e_n cap
# ---------------------------------------------------------------------------

def test_e_n_capped_at_15pct_edge():
    """edge=0.20 used to score e_n=133 — probable data errors floated to the
    top of the card. Capped: any edge >= 0.15 scores identically."""
    assert pick_score(0.62, 0.20) == pytest.approx(pick_score(0.62, 0.15))
    assert pick_score(0.62, 0.50) == pytest.approx(pick_score(0.62, 0.15))


def test_e_n_below_ceiling_unchanged():
    """Sub-ceiling edges keep the linear scale (no behavior change)."""
    assert pick_score(0.62, 0.06) < pick_score(0.62, 0.09) < pick_score(0.62, 0.15)
