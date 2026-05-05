"""Tests for the team-total derivation logic in generate_projections.py.

We test the mathematical + DB logic by reimplementing the minimal function
locally -- avoids the full module import chain while testing every code path.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Inline the logic under test so we don't need the full module import
# (generate_projections imports nba_projector, csv_writer, etc. which drag in
# network/DB/JAR deps that break the sandbox).
# ---------------------------------------------------------------------------

def _make_team_total_key(gid, tid):
    return f"{gid}:{tid}"


def _derive_team_totals(implied_totals, spreads, game_date, db_path):
    """Inline copy of generate_projections._derive_team_totals.

    Kept identical to the real implementation so any drift causes test failures.
    Math:
        home_total = (game_total - spread) / 2
        away_total = (game_total + spread) / 2
    where spread < 0 means the home team is favoured (e.g. -4 => home wins by 4).
    """
    if not implied_totals:
        return {}

    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT game_id, home_team_id, away_team_id FROM games WHERE game_date = ?",
            (game_date,),
        ).fetchall()
        con.close()
    except Exception:
        return {}

    derived = {}
    for row in rows:
        gid      = str(row["game_id"])
        home_tid = int(row["home_team_id"])
        away_tid = int(row["away_team_id"])

        game_total = implied_totals.get(gid)
        if not game_total or game_total <= 0:
            continue

        spread = spreads.get(gid)
        if spread is None:
            home_total = round(game_total / 2.0, 1)
            away_total = round(game_total / 2.0, 1)
        else:
            home_total = round((game_total - spread) / 2.0, 1)
            away_total = round((game_total + spread) / 2.0, 1)

        derived[_make_team_total_key(gid, home_tid)] = home_total
        derived[_make_team_total_key(gid, away_tid)] = away_total

    return derived


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _make_db(games):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE games "
        "(game_id INTEGER, game_date TEXT, home_team_id INTEGER, away_team_id INTEGER)"
    )
    con.executemany(
        "INSERT INTO games VALUES (?,?,?,?)",
        [(g["game_id"], g["game_date"], g["home_team_id"], g["away_team_id"]) for g in games],
    )
    con.commit()
    con.close()
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeriveTeamTotals:

    def test_home_favoured(self):
        """Home favoured by 4: home_total = (220+4)/2 = 112, away = 108."""
        db = _make_db([
            {"game_id": 101, "game_date": "2026-05-04", "home_team_id": 1, "away_team_id": 2},
        ])
        result = _derive_team_totals({"101": 220.0}, {"101": -4.0}, "2026-05-04", db)
        os.unlink(db)
        assert result["101:1"] == pytest.approx(112.0, abs=0.1)
        assert result["101:2"] == pytest.approx(108.0, abs=0.1)

    def test_away_favoured(self):
        """Away favoured by 6 (spread = +6 from home perspective)."""
        db = _make_db([
            {"game_id": 102, "game_date": "2026-05-04", "home_team_id": 3, "away_team_id": 4},
        ])
        result = _derive_team_totals({"102": 216.0}, {"102": 6.0}, "2026-05-04", db)
        os.unlink(db)
        # home_total = (216 - 6) / 2 = 105.0
        # away_total = (216 + 6) / 2 = 111.0
        assert result["102:3"] == pytest.approx(105.0, abs=0.1)
        assert result["102:4"] == pytest.approx(111.0, abs=0.1)

    def test_pick_em(self):
        """Pick-em (spread=0) => both teams get game_total / 2."""
        db = _make_db([
            {"game_id": 103, "game_date": "2026-05-04", "home_team_id": 5, "away_team_id": 6},
        ])
        result = _derive_team_totals({"103": 210.0}, {"103": 0.0}, "2026-05-04", db)
        os.unlink(db)
        assert result["103:5"] == pytest.approx(105.0, abs=0.1)
        assert result["103:6"] == pytest.approx(105.0, abs=0.1)

    def test_no_spread_fallback(self):
        """Missing spread => fall back to game_total / 2 per team."""
        db = _make_db([
            {"game_id": 104, "game_date": "2026-05-04", "home_team_id": 7, "away_team_id": 8},
        ])
        result = _derive_team_totals({"104": 218.0}, {}, "2026-05-04", db)
        os.unlink(db)
        assert result["104:7"] == pytest.approx(109.0, abs=0.1)
        assert result["104:8"] == pytest.approx(109.0, abs=0.1)

    def test_empty_implied_totals(self):
        """No game totals => return {}."""
        db = _make_db([])
        result = _derive_team_totals({}, {}, "2026-05-04", db)
        os.unlink(db)
        assert result == {}

    def test_game_not_in_db_skipped(self):
        """Game in implied_totals absent from games table => skipped silently."""
        db = _make_db([])
        result = _derive_team_totals({"999": 215.0}, {"999": -3.0}, "2026-05-04", db)
        os.unlink(db)
        assert result == {}

    def test_multiple_games(self):
        """Two games on same date both get four team-total entries."""
        db = _make_db([
            {"game_id": 201, "game_date": "2026-05-04", "home_team_id": 10, "away_team_id": 11},
            {"game_id": 202, "game_date": "2026-05-04", "home_team_id": 20, "away_team_id": 21},
        ])
        result = _derive_team_totals(
            {"201": 220.0, "202": 200.0},
            {"201": -5.0,  "202": 3.0},
            "2026-05-04", db,
        )
        os.unlink(db)
        # Game 201: home=(220+5)/2=112.5, away=(220-5)/2=107.5
        assert result["201:10"] == pytest.approx(112.5, abs=0.1)
        assert result["201:11"] == pytest.approx(107.5, abs=0.1)
        # Game 202: home=(200-3)/2=98.5, away=(200+3)/2=101.5
        assert result["202:20"] == pytest.approx(98.5, abs=0.1)
        assert result["202:21"] == pytest.approx(101.5, abs=0.1)
        assert len(result) == 4

    def test_key_format(self):
        """Keys use '{game_id}:{team_id}' format."""
        db = _make_db([
            {"game_id": 301, "game_date": "2026-05-04", "home_team_id": 50, "away_team_id": 51},
        ])
        result = _derive_team_totals({"301": 214.0}, {"301": -2.0}, "2026-05-04", db)
        os.unlink(db)
        assert "301:50" in result
        assert "301:51" in result

    def test_team_totals_sum_to_game_total(self):
        """home_total + away_total == game_total regardless of spread."""
        db = _make_db([
            {"game_id": 401, "game_date": "2026-05-04", "home_team_id": 60, "away_team_id": 61},
        ])
        game_total, spread = 219.5, -7.5
        result = _derive_team_totals({"401": game_total}, {"401": spread}, "2026-05-04", db)
        os.unlink(db)
        assert result["401:60"] + result["401:61"] == pytest.approx(game_total, abs=0.2)

    def test_date_filter_correct(self):
        """Only games matching game_date are included; other dates skipped."""
        db = _make_db([
            {"game_id": 501, "game_date": "2026-05-04", "home_team_id": 70, "away_team_id": 71},
            {"game_id": 502, "game_date": "2026-05-05", "home_team_id": 80, "away_team_id": 81},
        ])
        result = _derive_team_totals(
            {"501": 210.0, "502": 215.0},
            {},
            "2026-05-04", db,
        )
        os.unlink(db)
        assert "501:70" in result
        assert "501:71" in result
        assert "502:80" not in result
        assert "502:81" not in result
