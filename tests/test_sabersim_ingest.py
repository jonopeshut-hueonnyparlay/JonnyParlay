"""Tests for engine/sabersim_ingest.py -- write SaberSim slate projections into the
shared `projection` contract (source='sabersim').

Builds a minimal contract table (matching the real UNIQUE conflict key), ingests
synthetic players, and asserts: comparable markets only, MLB pitcher/batter market
selection, idempotent re-ingest, coexistence with source='edgemodel' rows, and
fail-soft on missing DB / absent table.
"""
import sqlite3
import time

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
_SLATE_DDL = (
    "CREATE TABLE slate ("
    " game_date TEXT NOT NULL, sport TEXT NOT NULL, entity_id TEXT NOT NULL,"
    " name TEXT, team TEXT, opponent TEXT, position TEXT, salary REAL,"
    " source TEXT NOT NULL DEFAULT 'sabersim',"
    " UNIQUE (game_date, sport, entity_id, source))"
)


# Contract variant WITH the #3 calibration governance columns.
_DDL_CAL = (
    "CREATE TABLE projection ("
    " run_id TEXT, game_date TEXT NOT NULL, sport TEXT NOT NULL,"
    " entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, market TEXT NOT NULL,"
    " source TEXT NOT NULL, model_version TEXT, mean REAL,"
    " calibration_method TEXT, calibration_version TEXT,"
    " UNIQUE (run_id, sport, market, entity_id, source))"
)


def _db_with_contract(tmp_path, with_slate=True, cal=False):
    db = tmp_path / "proj.db"
    conn = sqlite3.connect(db)
    conn.execute(_DDL_CAL if cal else _DDL)
    if with_slate:
        conn.execute(_SLATE_DDL)
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


def test_calibration_governance_stamped_per_sport(tmp_path):
    """#3: when the contract carries the calibration columns, SaberSim rows stamp the
    GOVERNING regime per sport -- NBA/WNBA Platt-calibrated, MLB skips Platt ('none')."""
    from calibrated import PLATT_FIT_DATE
    db = _db_with_contract(tmp_path, cal=True)
    si.ingest({"WNBA": [{"name": "A'ja Wilson", "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}],
               "MLB": [{"name": "Aaron Judge", "is_pitcher": False, "HITS": 1.2, "TB": 2.1, "HR": 0.4}]},
              "2026-06-26", db_path=db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        cal = {r["sport"]: (r["calibration_method"], r["calibration_version"])
               for r in conn.execute("SELECT DISTINCT sport, calibration_method, "
                                      "calibration_version FROM projection")}
        assert cal["WNBA"] == ("platt", PLATT_FIT_DATE)
        assert cal["MLB"] == ("none", None)  # Platt skipped for MLB
    finally:
        conn.close()


def test_pre_calibration_column_db_still_ingests(tmp_path):
    """#3 column-tolerance: a contract DB predating calibration_method still ingests via
    the base upsert (fail-soft, no crash)."""
    db = _db_with_contract(tmp_path, cal=False)  # no calibration columns
    n = si.ingest({"WNBA": [{"name": "A'ja Wilson", "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]},
                  "2026-06-26", db_path=db)
    assert n == 4


class _ExecuteSpyConn:
    """Thin proxy around a real sqlite3.Connection that records .execute() SQL
    text. sqlite3.Connection is an immutable C type -- can't monkeypatch its
    methods directly -- so we wrap sqlite3.connect()'s return value instead."""

    def __init__(self, real_conn, calls):
        object.__setattr__(self, "_real", real_conn)
        object.__setattr__(self, "_calls", calls)

    def execute(self, sql, *a, **k):
        self._calls.append(sql)
        return self._real.execute(sql, *a, **k)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)


def test_sets_busy_timeout_pragma(tmp_path, monkeypatch):
    """H4 hardening: ingest() must set PRAGMA busy_timeout on its own connection
    so a write lock held briefly by EdgeModel's own process doesn't fail this
    write immediately -- matches EdgeModel's own projections_db.py timeout."""
    db = _db_with_contract(tmp_path)
    calls = []
    real_connect = sqlite3.connect

    def spy_connect(*a, **k):
        return _ExecuteSpyConn(real_connect(*a, **k), calls)

    monkeypatch.setattr(sqlite3, "connect", spy_connect)
    si.ingest({"WNBA": [{"name": "A'ja Wilson", "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]},
              "2026-06-26", db_path=db)
    assert any("busy_timeout" in c.lower() for c in calls), \
        f"expected a PRAGMA busy_timeout call, got: {calls}"


def test_retries_on_lock_contention_then_succeeds(tmp_path, monkeypatch):
    """H5 hardening: a transient 'database is locked' error retries instead of
    giving up on the first attempt. Simulate 2 failures then a real success."""
    db = _db_with_contract(tmp_path)
    monkeypatch.setattr(time, "sleep", lambda s: None)  # don't actually wait in tests
    real_connect = sqlite3.connect
    attempts = {"n": 0}

    def flaky_connect(*a, **k):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(*a, **k)

    monkeypatch.setattr(sqlite3, "connect", flaky_connect)
    n = si.ingest({"WNBA": [{"name": "A'ja Wilson", "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]},
                  "2026-06-26", db_path=db)
    assert n == 4
    assert attempts["n"] == 3  # 2 failed attempts + 1 success, within _MAX_RETRIES


def test_gives_up_failsoft_when_always_locked(tmp_path, monkeypatch):
    """All attempts hit lock contention -> fail-soft 0, never raises."""
    db = _db_with_contract(tmp_path)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def always_locked(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(sqlite3, "connect", always_locked)
    n = si.ingest({"WNBA": [{"name": "X", "PTS": 1.0}]}, "2026-06-26", db_path=db)
    assert n == 0


def test_non_lock_exception_fails_soft_without_retrying(tmp_path, monkeypatch):
    """A non-lock error (e.g. a genuine bug) must fail soft immediately --
    only sqlite3.OperationalError gets the retry treatment."""
    db = _db_with_contract(tmp_path)
    attempts = {"n": 0}

    def boom(*a, **k):
        attempts["n"] += 1
        raise ValueError("not a lock issue")

    monkeypatch.setattr(sqlite3, "connect", boom)
    n = si.ingest({"WNBA": [{"name": "X", "PTS": 1.0}]}, "2026-06-26", db_path=db)
    assert n == 0
    assert attempts["n"] == 1  # no retry for non-lock errors


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


# --- #4 slate feed split ----------------------------------------------------

def _slate_rows(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return {r["entity_id"]: r for r in conn.execute(
            "SELECT entity_id, team, opponent, position, salary FROM slate")}
    finally:
        conn.close()


def test_ingest_writes_decoupled_slate_rows(tmp_path):
    db = _db_with_contract(tmp_path)
    players = [{"name": "A'ja Wilson", "team": "LV", "opp": "SEA", "pos": "F",
                "salary": 9800, "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]
    si.ingest({"WNBA": players}, "2026-06-26", db_path=db)
    row = _slate_rows(db)[name_key("A'ja Wilson")]
    assert (row["team"], row["opponent"], row["position"]) == ("LV", "SEA", "F")
    assert row["salary"] == 9800.0


def test_slate_absent_table_does_not_break_projection_write(tmp_path):
    # Older EdgeModel without the slate table: projections still write, slate skipped.
    db = _db_with_contract(tmp_path, with_slate=False)
    n = si.ingest({"WNBA": [{"name": "A'ja Wilson", "team": "LV", "opp": "SEA",
                             "PTS": 22.5, "REB": 9.1, "AST": 2.3, "3PM": 0.4}]},
                  "2026-06-26", db_path=db)
    assert n == 4  # projection rows still written despite no slate table
