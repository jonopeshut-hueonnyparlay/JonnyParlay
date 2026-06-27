"""Tests for engine/source_shadow_game_lines.py -- MLB game-line source shadow."""
import source_shadow_game_lines as gl

_PROJ = {("NYY", "BOS"): {"proj_total": 9.5, "p_home_win": 0.60}}  # keyed (HOME, AWAY)


def _fetch(date, db_path=None):
    return _PROJ


_ROWS = [
    # TOTAL over @8.5; EM proj_total 9.5 -> over; result W -> over hit; agree
    {"date": "2026-06-26", "sport": "MLB", "game": "BOS@NYY", "stat": "TOTAL",
     "line": "8.5", "direction": "over", "result": "W"},
    # TOTAL over @10.5; EM 9.5 -> under; result L -> under hit; disagree, EM right
    {"date": "2026-06-26", "sport": "MLB", "game": "BOS@NYY", "stat": "TOTAL",
     "line": "10.5", "direction": "over", "result": "L"},
    # ML home; p_home_win 0.60 -> EM home; result W -> home won; agree
    {"date": "2026-06-26", "sport": "MLB", "game": "BOS@NYY", "stat": "ML",
     "line": "0", "direction": "home", "result": "W"},
    # SPREAD not covered -> skipped
    {"date": "2026-06-26", "sport": "MLB", "game": "BOS@NYY", "stat": "SPREAD",
     "line": "-1.5", "direction": "home", "result": "W"},
    # no projection for this game -> skipped
    {"date": "2026-06-26", "sport": "MLB", "game": "TB@CIN", "stat": "TOTAL",
     "line": "8.5", "direction": "over", "result": "W"},
    # ungraded -> skipped
    {"date": "2026-06-26", "sport": "MLB", "game": "BOS@NYY", "stat": "ML",
     "line": "0", "direction": "away", "result": ""},
]


def test_total_and_ml_comparison_logic():
    comp = gl.compare_rows(_ROWS, fetch=_fetch)
    assert len(comp) == 3  # 2 TOTAL + 1 ML; SPREAD/no-proj/ungraded skipped
    by = {(r["market"], r["line"]): r for r in comp}

    t1 = by[("TOTAL", "8.5")]
    assert t1["em_side"] == "over" and t1["actual"] == "over" and t1["agree"] == 1 and t1["em_win"] == 1

    t2 = by[("TOTAL", "10.5")]
    assert t2["em_side"] == "under" and t2["actual"] == "under"
    assert t2["agree"] == 0 and t2["disagree_winner"] == "edgemodel"

    ml = by[("ML", "0")]
    assert ml["em_side"] == "home" and ml["actual"] == "home" and ml["agree"] == 1


def test_empty_projections_yields_nothing():
    assert gl.compare_rows(_ROWS, fetch=lambda *a, **k: {}) == []


def test_teams_parse():
    assert gl._teams("BOS@NYY") == ("NYY", "BOS")
    assert gl._teams("nope") == ("", "")
