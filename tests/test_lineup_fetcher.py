"""Tests for lineup_fetcher.py and the confirmed-starter integration in nba_projector."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_with_mocks(sb_return, bs_side_effect=None, bs_return=None):
    """Call fetch_confirmed_starters with mocked live API responses.

    sb_return: dict returned by ScoreBoard().get_dict()
    bs_side_effect: callable(game_id) that returns the BoxScore mock, or None
    bs_return: single BoxScore().get_dict() return value (used when bs_side_effect is None)
    """
    from lineup_fetcher import fetch_confirmed_starters

    sb_mock = MagicMock()
    sb_mock.ScoreBoard.return_value.get_dict.return_value = sb_return

    bs_mock = MagicMock()
    if bs_side_effect is not None:
        bs_mock.BoxScore.side_effect = bs_side_effect
    elif bs_return is not None:
        bs_mock.BoxScore.return_value.get_dict.return_value = bs_return

    with patch.dict("sys.modules", {
        "nba_api.live.nba.endpoints.scoreboard": sb_mock,
        "nba_api.live.nba.endpoints.boxscore": bs_mock,
    }):
        return fetch_confirmed_starters("2026-05-08")


def _sb(game_ids):
    return {"scoreboard": {"games": [{"gameId": gid} for gid in game_ids]}}


def _bs(home_tricode, home_names, away_tricode, away_names, home_starter=True, away_starter=True):
    def _players(names, is_starter):
        return [{"name": n, "starter": "1" if is_starter else "0"} for n in names]
    return {
        "game": {
            "homeTeam": {"teamTricode": home_tricode, "players": _players(home_names, home_starter)},
            "awayTeam": {"teamTricode": away_tricode, "players": _players(away_names, away_starter)},
        }
    }


# ---------------------------------------------------------------------------
# lineup_fetcher unit tests
# ---------------------------------------------------------------------------

def test_returns_empty_when_no_games():
    result = _call_with_mocks(sb_return=_sb([]))
    assert result == {}


def test_returns_empty_when_partial_starters():
    """Only 3 starters confirmed — not included in result."""
    three = ["A", "B", "C"]
    result = _call_with_mocks(
        sb_return=_sb(["001"]),
        bs_return=_bs("PHI", three, "NYK", []),
    )
    assert "PHI" not in result
    assert "NYK" not in result


def test_returns_starters_when_exactly_five():
    phi = ["A One", "B Two", "C Three", "D Four", "E Five"]
    nyk = ["F Six", "G Seven", "H Eight", "I Nine", "J Ten"]
    result = _call_with_mocks(
        sb_return=_sb(["001"]),
        bs_return=_bs("PHI", phi, "NYK", nyk),
    )
    assert result["PHI"] == phi
    assert result["NYK"] == nyk


def test_skips_game_on_boxscore_error():
    """A BoxScore error on one game doesn't abort others."""
    phi = ["A", "B", "C", "D", "E"]

    def bs_side_effect(game_id):
        if game_id == "001":
            raise ValueError("network error")
        m = MagicMock()
        m.get_dict.return_value = _bs("PHI", phi, "SAS", [])
        return m

    result = _call_with_mocks(
        sb_return=_sb(["001", "002"]),
        bs_side_effect=bs_side_effect,
    )
    assert result.get("PHI") == phi


def test_returns_empty_when_nba_api_missing():
    """Graceful degradation if nba_api not installed."""
    from lineup_fetcher import fetch_confirmed_starters
    fake = MagicMock()
    fake.ScoreBoard.side_effect = ImportError("no nba_api")
    # Simulate ImportError raised at the `from nba_api.live...` line
    with patch.dict("sys.modules", {
        "nba_api.live.nba.endpoints.scoreboard": None,
        "nba_api.live.nba.endpoints.boxscore": None,
    }):
        result = fetch_confirmed_starters("2026-05-08")
    assert result == {}


def test_ignores_game_with_no_game_id():
    sb_return = {"scoreboard": {"games": [{"gameId": ""}]}}
    result = _call_with_mocks(sb_return=sb_return)
    assert result == {}


# ---------------------------------------------------------------------------
# project_player confirmed-starter integration
# ---------------------------------------------------------------------------

def _make_db(tmp_path, season_type="Regular Season"):
    import sqlite3
    db = str(tmp_path / "test.db")
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS player_game_stats (
            player_id INTEGER, team_id INTEGER, game_id TEXT, game_date TEXT,
            min REAL, starter_flag INTEGER, pts REAL, reb REAL, ast REAL,
            fg3m REAL, blk REAL, stl REAL, tov REAL, fga REAL, fgm REAL,
            fta REAL, ftm REAL, fg3a REAL, poss REAL, season TEXT, season_type TEXT
        );
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY, abbreviation TEXT, name TEXT, city TEXT
        );
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY, game_date TEXT, home_team_id INTEGER,
            away_team_id INTEGER, season TEXT, season_type TEXT
        );
        CREATE TABLE IF NOT EXISTS projections (player_id INTEGER, game_date TEXT);
    """)
    conn.execute("INSERT INTO teams VALUES (101,'TST','Test','City')")
    conn.execute("INSERT INTO teams VALUES (102,'OPP','Opp','City')")
    conn.execute(
        f"INSERT INTO games VALUES ('g99','2026-05-08',101,102,'2025-26','{season_type}')"
    )
    conn.commit()
    conn.close()
    return db


_RATES = {
    "pts_rate": 0.5, "reb_rate": 0.2, "ast_rate": 0.1,
    "fg3m_rate": 0.05, "blk_rate": 0.02, "stl_rate": 0.03, "tov_rate": 0.04,
    "fga_rate": 0.9, "fgm_rate": 0.45, "fta_rate": 0.2, "ftm_rate": 0.16,
    "fg3a_rate": 0.2, "usg_rate": 0.25,
}


def _call_project_player(db, df, proj_min, is_confirmed_starter, season_type="Regular Season"):
    from unittest.mock import patch as mpatch
    import nba_projector as nbp

    with mpatch.object(nbp, "get_player_recent_games", return_value=df), \
         mpatch.object(nbp, "get_player_season_game_count", return_value=15), \
         mpatch.object(nbp, "get_player_b2b_context", return_value=False), \
         mpatch.object(nbp, "get_player_trade_context", return_value=None), \
         mpatch.object(nbp, "compute_availability_weights", return_value=None), \
         mpatch.object(nbp, "get_player_career_avg_minutes", return_value=None), \
         mpatch.object(nbp, "compute_per_minute_rates", return_value=_RATES), \
         mpatch.object(nbp, "project_minutes", return_value=proj_min), \
         mpatch.object(nbp, "get_team_pace", return_value=100.0), \
         mpatch.object(nbp, "get_team_def_ratio", return_value=1.0), \
         mpatch.object(nbp, "get_team_tov_rate", return_value=0.13), \
         mpatch.object(nbp, "get_team_rim_attempt_rate", return_value=0.25), \
         mpatch.object(nbp, "get_team_shooting_stats",
                       return_value={"fga_per_game": 88.0, "fg_pct": 0.46}), \
         mpatch.object(nbp, "get_team_avg_fga", return_value=88.0), \
         mpatch.object(nbp, "compute_shooting_rates", return_value={
             "fg2_pct": 0.50, "fg3_pct": 0.36, "fg3a_rate": 0.35,
             "ft_pct": 0.78, "fta_fga_ratio": 0.22, "usg_pct": 22.0,
         }):

        return nbp.project_player(
            player_id=1, player_name="Test Player", position="G",
            team_id=101, opp_team_id=102,
            game_id="g99", game_date="2026-05-08", season="2025-26",
            season_type=season_type, db_path=db,
            is_confirmed_starter=is_confirmed_starter,
        )


def test_confirmed_starter_promotes_rotation_to_starter(tmp_path):
    import pandas as pd
    db = _make_db(tmp_path, "Playoffs")
    # 8 games, avg 16 min, 0 starts → classify_role returns "rotation"
    df = pd.DataFrame({
        "min": [16.0] * 8, "starter_flag": [0] * 8,
        "game_date": [f"2026-04-{i+1:02d}" for i in range(8)],
    })
    proj = _call_project_player(db, df, proj_min=22.0,
                                is_confirmed_starter=True, season_type="Playoffs")
    assert proj is not None
    assert proj["role_tier"] == "starter"


def test_no_confirmed_data_leaves_role_unchanged(tmp_path):
    import pandas as pd
    db = _make_db(tmp_path)
    df = pd.DataFrame({
        "min": [16.0] * 8, "starter_flag": [0] * 8,
        "game_date": [f"2026-04-{i+1:02d}" for i in range(8)],
    })
    proj = _call_project_player(db, df, proj_min=14.0, is_confirmed_starter=None)
    assert proj is not None
    assert proj["role_tier"] == "rotation"


def test_lineup_mismatch_logged(tmp_path, caplog):
    """is_confirmed_starter=False with historically-starter player logs LINEUP-MISMATCH."""
    import pandas as pd
    import logging
    db = _make_db(tmp_path)
    # 8 games, avg 32 min, 100% starts → classify_role returns "starter"
    df = pd.DataFrame({
        "min": [32.0] * 8, "starter_flag": [1] * 8,
        "game_date": [f"2026-04-{i+1:02d}" for i in range(8)],
    })
    with caplog.at_level(logging.WARNING, logger="jonnyparlay"):
        proj = _call_project_player(db, df, proj_min=32.0, is_confirmed_starter=False)
    assert proj is not None
    assert proj["role_tier"] == "starter"  # no downgrade
    assert any("LINEUP-MISMATCH" in r.message for r in caplog.records)


def test_confirmed_starter_does_not_affect_cold_start(tmp_path):
    """Cold-start players stay cold_start regardless of confirmed_starter flag."""
    import pandas as pd
    from unittest.mock import patch as mpatch
    import nba_projector as nbp

    db = _make_db(tmp_path, "Playoffs")
    df = pd.DataFrame({"min": [], "starter_flag": [], "game_date": []})

    with mpatch.object(nbp, "get_player_recent_games", return_value=df), \
         mpatch.object(nbp, "get_player_season_game_count", return_value=3), \
         mpatch.object(nbp, "get_player_b2b_context", return_value=False), \
         mpatch.object(nbp, "get_player_trade_context", return_value=None), \
         mpatch.object(nbp, "compute_availability_weights", return_value=None), \
         mpatch.object(nbp, "get_player_career_avg_minutes", return_value=None), \
         mpatch.object(nbp, "get_player_career_game_count", return_value=(0, None)), \
         mpatch.object(nbp, "get_player_last_appearance_days", return_value=None), \
         mpatch.object(nbp, "compute_per_minute_rates", return_value=_RATES), \
         mpatch.object(nbp, "project_minutes", return_value=10.0), \
         mpatch.object(nbp, "get_team_pace", return_value=100.0), \
         mpatch.object(nbp, "get_team_def_ratio", return_value=1.0), \
         mpatch.object(nbp, "get_team_tov_rate", return_value=0.13), \
         mpatch.object(nbp, "get_team_rim_attempt_rate", return_value=0.25), \
         mpatch.object(nbp, "get_team_shooting_stats",
                       return_value={"fga_per_game": 88.0, "fg_pct": 0.46}), \
         mpatch.object(nbp, "get_team_avg_fga", return_value=88.0), \
         mpatch.object(nbp, "compute_shooting_rates", return_value={
             "fg2_pct": 0.50, "fg3_pct": 0.36, "fg3a_rate": 0.35,
             "ft_pct": 0.78, "fta_fga_ratio": 0.22, "usg_pct": 22.0,
         }):

        proj = nbp.project_player(
            player_id=1, player_name="Test Player", position="G",
            team_id=101, opp_team_id=102,
            game_id="g99", game_date="2026-05-08", season="2025-26",
            season_type="Playoffs", db_path=db,
            is_confirmed_starter=True,
        )
    # cold_start path doesn't enter the confirmed-starter override block
    assert proj is not None
    assert proj["role_tier"] == "cold_start"
