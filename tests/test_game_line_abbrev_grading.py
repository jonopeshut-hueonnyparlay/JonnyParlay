"""test_game_line_abbrev_grading.py — regression for the game-line grading bug.

pick_log_game_lines.csv stores the `game` field as 'AWAY@HOME' using team
ABBREVIATIONS with no spaces (e.g. 'MIL@ATH'), while fetch_scores() /
fetch_mlb_linescores() key games by FULL team names ('Milwaukee Brewers @
Athletics'). The old matcher bridged neither, so every game-line row graded
None despite scores being available. Additionally, the writer never persisted
the `line` column, so grade_game_line() bailed at float('').

These pin:
  - _resolve_score_game(): abbreviation 'AWAY@HOME' → full-name score game
  - _find_linescore_innings(): abbreviation fallback for F5/NRFI linescores
  - grade_game_line(): moneyline stats grade with a blank line; line-dependent
    stats grade once a line is present
  - analyze_game_lines._line_from_label(): recovers the line from the label

Pure-function tests — no network, no Discord, no filesystem.

Run:
    python -m pytest tests/test_game_line_abbrev_grading.py -v
"""

import grade_picks as gp  # noqa: E402  (engine/ on path via conftest)


def _score_game(away_full, away_score, home_full, home_score):
    """Shape returned by fetch_scores() → scores_by_game values."""
    return {
        "home_team": home_full,
        "away_team": away_full,
        "completed": True,
        "scores": [
            {"name": home_full, "score": str(home_score)},
            {"name": away_full, "score": str(away_score)},
        ],
    }


# Milwaukee @ Athletics: away 5, home 2  (away win)
SCORES = {
    "Milwaukee Brewers @ Athletics": _score_game("Milwaukee Brewers", 5, "Athletics", 2),
    "Chicago Cubs @ Colorado Rockies": _score_game("Chicago Cubs", 3, "Colorado Rockies", 9),
}


def _pick(stat, direction, line, game="MIL@ATH", team="ATH", is_home="0", sport="MLB"):
    return {
        "sport": sport, "game": game, "player": game, "team": team,
        "stat": stat, "direction": direction, "line": line, "is_home": is_home,
    }


# ── _resolve_score_game: abbreviation match ──────────────────────────────────

def test_resolve_score_game_matches_abbreviation():
    g = gp._resolve_score_game(_pick("TOTAL", "over", "7.5"), SCORES)
    assert g is not None
    assert g["home_team"] == "Athletics" and g["away_team"] == "Milwaukee Brewers"


def test_resolve_score_game_full_name_still_works():
    pick = _pick("TOTAL", "over", "7.5", game="Milwaukee Brewers @ Athletics")
    g = gp._resolve_score_game(pick, SCORES)
    assert g is not None and g["home_team"] == "Athletics"


def test_resolve_score_game_no_false_match_on_single_team():
    # 'ATH' alone must not match — both abbreviations must resolve to the pair.
    pick = _pick("TOTAL", "over", "7.5", game="ATH@XYZ")
    assert gp._resolve_score_game(pick, SCORES) is None


# ── grade_game_line: line-dependent stats ────────────────────────────────────

def test_total_grades_with_line():
    # away 5 + home 2 = 7 total; over 7.5 loses, over 6.5 wins
    assert gp.grade_game_line(_pick("TOTAL", "over", "7.5"), SCORES) == "L"
    assert gp.grade_game_line(_pick("TOTAL", "over", "6.5"), SCORES) == "W"


def test_team_total_grades_with_line():
    # Athletics (home) scored 2; under 4.5 wins
    assert gp.grade_game_line(_pick("TEAM_TOTAL", "under", "4.5", is_home="1"), SCORES) == "W"


def test_spread_grades_with_line():
    # Rockies (home) won 9-3; home -3.5 covers → W
    pick = _pick("SPREAD", "home", "-3.5", game="CHC@COL", team="COL", is_home="1")
    assert gp.grade_game_line(pick, SCORES) == "W"


# ── grade_game_line: moneyline tolerates a blank line ────────────────────────

def test_moneyline_grades_with_blank_line():
    # ML_DOG on away team (Milwaukee won 5-2); blank line must not bail.
    pick = _pick("ML_DOG", "away", "", is_home="0")
    assert gp.grade_game_line(pick, SCORES) == "W"


def test_line_dependent_stat_blank_line_is_ungradable():
    # TOTAL with no line genuinely cannot be graded → None (not a crash).
    assert gp.grade_game_line(_pick("TOTAL", "over", ""), SCORES) is None


def test_plain_ml_stat_grades():
    # analyze_game_lines.py writes stat='ML' (not ML_FAV/ML_DOG) — the grader
    # must handle it. Milwaukee (away) won 5-2.
    assert gp.grade_game_line(_pick("ML", "away", "", is_home="0"), SCORES) == "W"
    assert gp.grade_game_line(_pick("ML", "home", "", is_home="1"), SCORES) == "L"


def test_plain_ml_in_game_line_stats():
    assert "ML" in gp.GAME_LINE_STATS
    assert "ML" in gp._MONEYLINE_STATS


# ── fetch_scores sport coverage ──────────────────────────────────────────────

def test_sport_keys_cover_live_sports():
    # Missing WNBA here made fetch_scores('WNBA', ...) return [] →
    # "0 completed games found" despite games being played.
    for sport, key in [("NBA", "basketball_nba"), ("MLB", "baseball_mlb"),
                       ("NHL", "icehockey_nhl"), ("WNBA", "basketball_wnba")]:
        assert gp.SPORT_KEYS.get(sport) == key


# ── _find_linescore_innings: abbreviation fallback ───────────────────────────

def test_find_linescore_innings_abbreviation_fallback():
    innings = [
        {"num": 1, "away": {"runs": 0}, "home": {"runs": 0}},
        {"num": 2, "away": {"runs": 1}, "home": {"runs": 0}},
    ]
    linescores = {
        "milwaukee brewers @ athletics": {"innings": innings, "is_final": True},
    }
    got = gp._find_linescore_innings("MIL@ATH", linescores)
    assert got is not None
    assert got[0] == innings and got[1] is True


# ── analyze_game_lines._line_from_label ──────────────────────────────────────

def test_line_from_label_extraction():
    import analyze_game_lines as agl
    assert agl._line_from_label("SPREAD HOME ATH (-1.5)") == "-1.5"
    assert agl._line_from_label("TOTAL OVER  (8.5)") == "8.5"
    assert agl._line_from_label("TT OVER  COL (4.5)") == "4.5"
    assert agl._line_from_label("F5 SPREAD AWAY MIL (+0.5)") == "+0.5"
    assert agl._line_from_label("ML HOME  ATH") == ""  # moneyline: no line


if __name__ == "__main__":
    import sys
    sys.exit(__import__("pytest").main([__file__, "-v"]))
