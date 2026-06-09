"""test_capture_clv_stat_markets.py — 2026-06-09 CLV capture-gap audit fixes.

Covers:
  - STAT_TO_MARKET: combo props (PA/PR/RA/PRA) + latent stats (ER/RBI/RUNS/
    GOALS/NHLPTS/NHLBLK/SV/BB) mapped to real Odds API market keys
  - GAME_LINE_MARKET: F5 stats point at *_1st_5_innings (full-game keys never
    matched an F5 line); TEAM_TOTAL + NRFI/YRFI mapped
  - SKIP_STATS: only truly market-less stats remain (GOLF_WIN/PARLAY/GA/PC)
  - get_closing_odds_for_pick: combo prop matching, TEAM_TOTAL team-filtered
    matching (same-city collision, accents, legacy blank is_home), NRFI
  - _is_capturable_stat guard: unmapped stats never enter the capture queue

Run:
    python -m pytest tests/test_capture_clv_stat_markets.py -v
"""

import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import capture_clv  # noqa: E402

# A guaranteed Colorado-legal book key for synthetic outcomes.
_BOOK = next(iter(capture_clv.CO_LEGAL_BOOKS))


def _oc(name, price, point=None, description="", book=_BOOK):
    return {"name": name, "description": description, "price": price,
            "point": point, "book": book}


# ── Market mappings ────────────────────────────────────────────────────────────

def test_combo_stats_mapped():
    m = capture_clv.STAT_TO_MARKET
    assert m["PRA"] == "player_points_rebounds_assists"
    assert m["PR"] == "player_points_rebounds"
    assert m["PA"] == "player_points_assists"
    assert m["RA"] == "player_rebounds_assists"


def test_latent_stats_mapped():
    m = capture_clv.STAT_TO_MARKET
    assert m["ER"] == "pitcher_earned_runs"
    assert m["BB"] == "pitcher_walks"
    assert m["RBI"] == "batter_rbis"
    assert m["RUNS"] == "batter_runs_scored"
    assert m["GOALS"] == "player_goals"
    assert m["NHLPTS"] == "player_points"
    assert m["NHLBLK"] == "player_blocked_shots"
    assert m["SV"] == "player_total_saves"


def test_f5_prop_log_keys_are_first_five_innings():
    m = capture_clv.GAME_LINE_MARKET
    assert m["F5_TOTAL"] == "totals_1st_5_innings"
    assert m["F5_SPREAD"] == "spreads_1st_5_innings"
    assert m["F5_ML"] == "h2h_1st_5_innings"


def test_team_total_and_first_inning_mapped():
    m = capture_clv.GAME_LINE_MARKET
    assert m["TEAM_TOTAL"] == "team_totals"
    assert m["NRFI"] == "totals_1st_1_innings"
    assert m["YRFI"] == "totals_1st_1_innings"


def test_skip_stats_only_marketless():
    assert capture_clv.SKIP_STATS == {"GOLF_WIN", "PARLAY", "GA", "PC"}


# ── Combo prop matching ────────────────────────────────────────────────────────

def test_combo_pra_matching():
    pick = {"stat": "PRA", "direction": "under", "line": "13.5",
            "player": "Cason Wallace"}
    outcomes = {"player_points_rebounds_assists": [
        _oc("Under", -110, 13.5, "Cason Wallace"),
        _oc("Over", -115, 13.5, "Cason Wallace"),
        _oc("Under", +150, 13.5, "Jalen Williams"),  # other player — ignore
    ]}
    odds, book = capture_clv.get_closing_odds_for_pick(pick, outcomes)
    assert odds == -110 and book == _BOOK


def test_combo_line_tolerance():
    pick = {"stat": "RA", "direction": "over", "line": "5.5",
            "player": "Alex Caruso"}
    outcomes = {"player_rebounds_assists": [
        _oc("Over", -105, 6.5, "Alex Caruso"),  # line moved a full point — no match
    ]}
    odds, _ = capture_clv.get_closing_odds_for_pick(pick, outcomes)
    assert odds is None


# ── TEAM_TOTAL matching ────────────────────────────────────────────────────────

_TT_OUTCOMES = {"team_totals": [
    _oc("Over", -120, 4.5, "Los Angeles Angels"),
    _oc("Under", +100, 4.5, "Los Angeles Angels"),
    _oc("Over", -110, 5.5, "Los Angeles Dodgers"),
    _oc("Under", -110, 5.5, "Los Angeles Dodgers"),
]}


def test_team_total_same_city_collision():
    """Any-word matching would cross LAA/LAD — require ALL words."""
    pick = {"stat": "TEAM_TOTAL", "direction": "over", "line": "4.5",
            "player": "Los Angeles Angels Team Total", "is_home": "True"}
    odds, _ = capture_clv.get_closing_odds_for_pick(
        pick, _TT_OUTCOMES,
        home_team="Los Angeles Angels", away_team="Los Angeles Dodgers")
    assert odds == -120


def test_team_total_away_side():
    pick = {"stat": "TEAM_TOTAL", "direction": "under", "line": "5.5",
            "player": "Los Angeles Dodgers Team Total", "is_home": "False"}
    odds, _ = capture_clv.get_closing_odds_for_pick(
        pick, _TT_OUTCOMES,
        home_team="Los Angeles Angels", away_team="Los Angeles Dodgers")
    assert odds == -110


def test_team_total_legacy_blank_is_home_uses_player_field():
    pick = {"stat": "TEAM_TOTAL", "direction": "over", "line": "4.5",
            "player": "Los Angeles Angels Team Total", "is_home": ""}
    odds, _ = capture_clv.get_closing_odds_for_pick(pick, _TT_OUTCOMES)
    assert odds == -120


def test_team_total_accent_folding():
    """'Montréal' in the log must match 'Montreal' from the API."""
    pick = {"stat": "TEAM_TOTAL", "direction": "under", "line": "3.5",
            "player": "Montréal Canadiens Team Total", "is_home": ""}
    outcomes = {"team_totals": [
        _oc("Under", -134, 3.5, "Montreal Canadiens"),
    ]}
    odds, _ = capture_clv.get_closing_odds_for_pick(pick, outcomes)
    assert odds == -134


def test_team_total_line_mismatch_skipped():
    pick = {"stat": "TEAM_TOTAL", "direction": "over", "line": "3.5",
            "player": "Los Angeles Angels Team Total", "is_home": "True"}
    odds, _ = capture_clv.get_closing_odds_for_pick(
        pick, _TT_OUTCOMES,
        home_team="Los Angeles Angels", away_team="Los Angeles Dodgers")
    assert odds is None  # only 4.5 on the board


# ── NRFI / YRFI ────────────────────────────────────────────────────────────────

def test_nrfi_matching():
    pick = {"stat": "NRFI", "direction": "under", "line": "0.5",
            "player": "NRFI"}
    outcomes = {"totals_1st_1_innings": [
        _oc("Under", -125, 0.5),
        _oc("Over", -105, 0.5),
    ]}
    odds, _ = capture_clv.get_closing_odds_for_pick(pick, outcomes)
    assert odds == -125


def test_yrfi_matching():
    pick = {"stat": "YRFI", "direction": "over", "line": "0.5",
            "player": "YRFI"}
    outcomes = {"totals_1st_1_innings": [
        _oc("Under", -125, 0.5),
        _oc("Over", -105, 0.5),
    ]}
    odds, _ = capture_clv.get_closing_odds_for_pick(pick, outcomes)
    assert odds == -105


# ── Unmapped-stat guard ────────────────────────────────────────────────────────

def _pick_row(stat, **kw):
    row = {"stat": stat, "closing_odds": "", "result": "", "run_type": "primary"}
    row.update(kw)
    return row


def test_unmapped_stat_never_queued():
    picks = [_pick_row("PRA"), _pick_row("WEIRD_STAT"), _pick_row("GA"),
             _pick_row("TEAM_TOTAL"), _pick_row("PARLAY")]
    queued = capture_clv.picks_needing_clv(picks)
    stats = {p["stat"] for p in queued}
    assert stats == {"PRA", "TEAM_TOTAL"}


def test_unmapped_stat_warns_once():
    capture_clv._warned_unmapped_stats.discard("ONE_SHOT_STAT")
    assert not capture_clv._is_capturable_stat("ONE_SHOT_STAT")
    assert "ONE_SHOT_STAT" in capture_clv._warned_unmapped_stats


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
