"""Tests for engine/edgemodel_adapter.py -- the read-side EdgeModel projections.db adapter.

Builds a minimal temp projections.db (only the columns the adapter selects) and
verifies normalization to JonnyParlay stat codes, the WNBA/NBA sport filter, MLB
pitcher+batter tables, and fail-soft on missing DB / unknown sport. No network, no
real DB.
"""
import sqlite3

import edgemodel_adapter as ea
from name_utils import name_key


def _make_db(tmp_path):
    db = tmp_path / "proj.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE projections (run_date TEXT, sport TEXT, player_name TEXT, "
        "proj_pts REAL, proj_reb REAL, proj_ast REAL, proj_fg3m REAL)")
    conn.executemany(
        "INSERT INTO projections VALUES (?,?,?,?,?,?,?)",
        [("2026-06-26", "WNBA", "A'ja Wilson", 22.5, 9.1, 2.3, 0.4),
         ("2026-06-26", "NBA", "Nikola Jokic", 28.0, 12.0, 9.0, 1.1),
         ("2026-06-25", "WNBA", "Old Game", 10.0, 5.0, 5.0, 1.0)])  # different date
    conn.execute(
        "CREATE TABLE mlb_batter_projections (run_date TEXT, batter_name TEXT, "
        "proj_hits REAL, proj_tb REAL, proj_hr REAL)")
    conn.execute("INSERT INTO mlb_batter_projections VALUES ('2026-06-26','Aaron Judge',1.2,2.1,0.4)")
    conn.execute(
        "CREATE TABLE mlb_pitcher_projections (run_date TEXT, pitcher_name TEXT, "
        "proj_k REAL, proj_outs REAL, proj_er REAL, proj_ha REAL, proj_bb REAL)")
    conn.execute("INSERT INTO mlb_pitcher_projections VALUES ('2026-06-26','Tarik Skubal',7.8,18.5,2.3,5.1,1.6)")
    conn.commit()
    conn.close()
    return db


def test_fetch_wnba_normalizes_and_filters_sport_and_date(tmp_path):
    res = ea.fetch("WNBA", "2026-06-26", db_path=_make_db(tmp_path))
    aja = name_key("A'ja Wilson")
    assert res[(aja, "PTS")] == 22.5
    assert res[(aja, "REB")] == 9.1
    assert res[(aja, "3PM")] == 0.4
    # NBA row excluded by the sport filter; the 06-25 WNBA row excluded by date.
    assert (name_key("Nikola Jokic"), "PTS") not in res
    assert (name_key("Old Game"), "PTS") not in res


def test_fetch_nba_uses_sport_filter(tmp_path):
    res = ea.fetch("NBA", "2026-06-26", db_path=_make_db(tmp_path))
    assert res[(name_key("Nikola Jokic"), "AST")] == 9.0
    assert (name_key("A'ja Wilson"), "PTS") not in res


def test_fetch_mlb_reads_both_pitcher_and_batter(tmp_path):
    res = ea.fetch("MLB", "2026-06-26", db_path=_make_db(tmp_path))
    assert res[(name_key("Aaron Judge"), "HITS")] == 1.2
    assert res[(name_key("Aaron Judge"), "TB")] == 2.1
    assert res[(name_key("Aaron Judge"), "HR")] == 0.4
    assert res[(name_key("Tarik Skubal"), "K")] == 7.8
    assert res[(name_key("Tarik Skubal"), "OUTS")] == 18.5


def test_missing_db_is_failsoft(tmp_path):
    assert ea.fetch("WNBA", "2026-06-26", db_path=tmp_path / "nope.db") == {}


def test_unknown_sport_is_empty(tmp_path):
    assert ea.fetch("XFL", "2026-06-26", db_path=_make_db(tmp_path)) == {}
