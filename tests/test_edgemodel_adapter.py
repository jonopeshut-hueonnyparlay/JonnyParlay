"""Tests for engine/edgemodel_adapter.py -- the read-side EdgeModel projections.db adapter.

Builds a minimal temp projections.db (only the columns the adapter selects) and
verifies normalization to JonnyParlay stat codes, the WNBA/NBA sport filter, MLB
pitcher+batter tables, and fail-soft on missing DB / unknown sport. No network, no
real DB.
"""
import logging
import sqlite3

import pytest

import edgemodel_adapter as ea
from name_utils import name_key


@pytest.fixture
def jonnyparlay_log(caplog):
    """The "jonnyparlay" logger sets propagate=False (engine_logger.py) so
    caplog's default root-logger handler never sees its records -- attach the
    capture handler directly, same pattern as
    tests/test_log_picks_zero_row_warning.py's jonnyparlay_warnings fixture."""
    logger = logging.getLogger("jonnyparlay")
    handler = caplog.handler
    logger.addHandler(handler)
    prev_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        yield caplog
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)


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


# --- contract-first read (the unification backbone, #3) ---------------------

def _add_contract(db, rows):
    """Add the minimal `projection` contract table + rows (game_date, sport,
    entity_id, market, source, mean) to an existing temp DB."""
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS projection (game_date TEXT, sport TEXT, "
        "entity_id TEXT, market TEXT, source TEXT, mean REAL)")
    conn.executemany("INSERT INTO projection VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_contract_read_used_when_present_and_equals_per_sport(tmp_path):
    db = _make_db(tmp_path)
    per_sport = ea.fetch("WNBA", "2026-06-26", db_path=db)   # contract absent -> per-sport
    # Populate the contract with the SAME numbers EdgeModel would write.
    aja = name_key("A'ja Wilson")
    _add_contract(db, [
        ("2026-06-26", "WNBA", aja, "PTS", "edgemodel", 22.5),
        ("2026-06-26", "WNBA", aja, "REB", "edgemodel", 9.1),
        ("2026-06-26", "WNBA", aja, "AST", "edgemodel", 2.3),
        ("2026-06-26", "WNBA", aja, "3PM", "edgemodel", 0.4),
    ])
    via_contract = ea.fetch("WNBA", "2026-06-26", db_path=db)
    assert via_contract == per_sport            # byte-identical reader switch


def test_contract_ignores_other_sources_and_sports(tmp_path):
    db = _make_db(tmp_path)
    aja = name_key("A'ja Wilson")
    _add_contract(db, [
        ("2026-06-26", "WNBA", aja, "PTS", "edgemodel", 22.5),
        ("2026-06-26", "WNBA", aja, "PTS", "sabersim", 99.9),   # other source ignored
        ("2026-06-26", "NBA", aja, "PTS", "edgemodel", 88.8),   # other sport ignored
    ])
    res = ea.fetch("WNBA", "2026-06-26", db_path=db)
    assert res[(aja, "PTS")] == 22.5


def test_falls_back_to_per_sport_when_contract_empty_for_date(tmp_path):
    db = _make_db(tmp_path)
    # Contract has a row for a different date only -> this slate falls back.
    _add_contract(db, [("2026-06-20", "WNBA", name_key("A'ja Wilson"), "PTS", "edgemodel", 1.0)])
    res = ea.fetch("WNBA", "2026-06-26", db_path=db)
    assert res[(name_key("A'ja Wilson"), "PTS")] == 22.5   # per-sport value, not the contract's


# ADR-005 / 1A (revised per architecture review): the contract query's existing
# `except sqlite3.OperationalError` is the real safety net here (schema_version
# comparison was dropped -- nothing bumps it, and the exception path already
# catches structural drift). These tests confirm it, and that "table absent"
# vs. "column absent" now log at different levels without changing behavior.

def test_contract_table_absent_is_debug_logged_not_warned(tmp_path, jonnyparlay_log):
    # _make_db() never creates the `projection` table at all -- every other
    # test in this file already exercises this path implicitly; this test
    # makes the log-level distinction explicit and asserts on it directly.
    db = _make_db(tmp_path)
    res = ea.fetch("WNBA", "2026-06-26", db_path=db)
    assert res[(name_key("A'ja Wilson"), "PTS")] == 22.5  # per-sport fallback still works
    assert any("not yet present" in r.message for r in jonnyparlay_log.records)
    assert not any(r.levelname == "WARNING" and "contract query failed" in r.message
                   for r in jonnyparlay_log.records)


def test_contract_column_missing_falls_back_gracefully(tmp_path, jonnyparlay_log):
    # A `projection` table that exists but is missing the `mean` column --
    # structural drift, not simple absence. Must still fail soft (fall back to
    # the per-sport tables), not crash -- and should warn, not debug-log.
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE projection (game_date TEXT, sport TEXT, "
        "entity_id TEXT, market TEXT, source TEXT)")  # no `mean` column
    conn.execute(
        "INSERT INTO projection VALUES ('2026-06-26','WNBA',?,'PTS','edgemodel')",
        (name_key("A'ja Wilson"),))
    conn.commit()
    conn.close()
    res = ea.fetch("WNBA", "2026-06-26", db_path=db)
    assert res[(name_key("A'ja Wilson"), "PTS")] == 22.5  # per-sport fallback still works
    assert any(r.levelname == "WARNING" and "contract query failed" in r.message
               for r in jonnyparlay_log.records)
