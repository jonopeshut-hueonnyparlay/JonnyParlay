"""Tests for engine/sabersim_ingest.py -- write SaberSim slate projections into the
shared `projection` contract (source='sabersim').

Builds a minimal contract table (matching the real UNIQUE conflict key), ingests
synthetic players, and asserts: comparable markets only, MLB pitcher/batter market
selection, idempotent re-ingest, coexistence with source='edgemodel' rows, and
fail-soft on missing DB / absent table.
"""
import sqlite3

import sabersim_ingest as si
from name_utils import name_key

# The contract columns the writer touches + the UNIQUE key it upserts on.
_DDL = (
    "CREATE TABLE projection ("
    " run_id TEXT, game_date TEXT NOT NULL, sport TEXT NOT NULL,"
    " entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, market TEXT NOT NULL,"
    " source TEXT NOT NULL, model_version TEXT, mean REAL,"
    " UNIQUE (run_id, sport, market, entity_id, source))"
)


def _db_with_contract(tmp_path):
    db = tmp_path / "proj.db"
    conn = sqlite3.connect(db)
    conn.execute(_DDL)
    conn.commit()
    conn.close()
    return db


def _rows(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return {(r["entity_id"], r["market"], r["source"]): r["mean"]
                for r in conn.execute("SELECT entity_id, market, source, mean FROM projection")}
    finally:
        conn.close()


def test_basketball_writes_comparable_markets(tmp_path):
    db = _db_with_contract(tmp_path)
    players = [{"name": "A'ja Wilson", "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]
    n = si.ingest({"WNBA": players}, "2026-06-26", db_path=db)
    assert n == 4
    aja = name_key("A'ja Wilson")
    got = _rows(db)
    assert got[(aja, "PTS", "sabersim")] == 22.5
    assert got[(aja, "3PM", "sabersim")] == 0.4


def test_mlb_pitcher_and_batter_market_split(tmp_path):
    db = _db_with_contract(tmp_path)
    players = [
        {"name": "Tarik Skubal", "is_pitcher": True,
         "K": 7.8, "OUTS": 18.5, "ER": 2.3, "HA": 5.1, "BB": 1.6, "HR": 0.9},
        {"name": "Aaron Judge", "is_pitcher": False, "HITS": 1.2, "TB": 2.1, "HR": 0.4},
    ]
    si.ingest({"MLB": players}, "2026-06-26", db_path=db)
    got = _rows(db)
    sk, judge = name_key("Tarik Skubal"), name_key("Aaron Judge")
    # pitcher: K/OUTS/ER/HA/BB only -- NOT HR (mirrors EdgeModel's pitcher contract map)
    assert got[(sk, "K", "sabersim")] == 7.8
    assert (sk, "HR", "sabersim") not in got
    # batter: HITS/TB/HR
    assert got[(judge, "HR", "sabersim")] == 0.4
    assert (judge, "K", "sabersim") not in got


def test_idempotent_reingest_upserts_in_place(tmp_path):
    db = _db_with_contract(tmp_path)
    si.ingest({"WNBA": [{"name": "A'ja Wilson", "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]},
              "2026-06-26", db_path=db)
    # Re-ingest the same slate with a changed value -> updates, no duplicate rows.
    si.ingest({"WNBA": [{"name": "A'ja Wilson", "PTS": 25.0, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]},
              "2026-06-26", db_path=db)
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM projection").fetchone()[0] == 4
        pts = conn.execute(
            "SELECT mean FROM projection WHERE market='PTS' AND source='sabersim'").fetchone()[0]
        assert pts == 25.0
    finally:
        conn.close()


def test_coexists_with_edgemodel_source(tmp_path):
    db = _db_with_contract(tmp_path)
    aja = name_key("A'ja Wilson")
    # Pre-seed an EdgeModel row for the same (date, sport, market, entity).
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO projection(run_id, game_date, sport, entity_type, entity_id, "
                 "market, source, mean) VALUES('em|r1','2026-06-26','WNBA','player',?,'PTS',"
                 "'edgemodel',21.0)", (aja,))
    conn.commit()
    conn.close()
    si.ingest({"WNBA": [{"name": "A'ja Wilson", "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]},
              "2026-06-26", db_path=db)
    got = _rows(db)
    # Both sources present for the same player/market -> directly comparable.
    assert got[(aja, "PTS", "edgemodel")] == 21.0
    assert got[(aja, "PTS", "sabersim")] == 22.5


def test_missing_db_is_failsoft(tmp_path):
    assert si.ingest({"WNBA": [{"name": "X", "PTS": 1.0}]}, "2026-06-26",
                     db_path=tmp_path / "nope.db") == 0


def test_absent_contract_table_is_failsoft(tmp_path):
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()  # exists but no `projection` table
    assert si.ingest({"WNBA": [{"name": "X", "PTS": 1.0}]}, "2026-06-26", db_path=db) == 0


def test_unknown_sport_writes_nothing(tmp_path):
    db = _db_with_contract(tmp_path)
    assert si.ingest({"XFL": [{"name": "X", "PTS": 1.0}]}, "2026-06-26", db_path=db) == 0
