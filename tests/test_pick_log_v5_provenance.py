"""Tests for pick_log v5 -- per-bet source provenance (source/model_version/run_id).

Covers the schema bump (append-only, blank-fill migration), the resolver source
decision, the primary writer emitting provenance, and the bet_lineage mirror.
"""
import csv
import sqlite3
import time

import pick_log_schema as pls


# ── schema (v5, append-only) ────────────────────────────────────────────────

def test_schema_version_and_header():
    assert pls.SCHEMA_VERSION == 6
    # v5 provenance trio followed by the v6 clv_corrected column.
    assert pls.CANONICAL_HEADER[-4:] == ["source", "model_version", "run_id", "clv_corrected"]
    assert pls.LIVE_SOURCE == "sabersim"


def test_detect_v6_v5_and_v4():
    assert pls.detect_schema_version(pls.CANONICAL_HEADER) == 6
    v5 = [c for c in pls.CANONICAL_HEADER if c != "clv_corrected"]
    assert pls.detect_schema_version(v5) == 5
    v4 = [c for c in v5 if c not in ("source", "model_version", "run_id")]
    assert pls.detect_schema_version(v4) == 4


def test_migrate_v4_row_blank_fills_v5_columns():
    v4_row = {c: "x" for c in pls.CANONICAL_HEADER
              if c not in ("source", "model_version", "run_id")}
    out = pls.migrate_row(v4_row)
    assert out["source"] == "" and out["model_version"] == "" and out["run_id"] == ""
    assert out["date"] == "x"  # existing columns preserved


# ── resolver source decision ────────────────────────────────────────────────

def _write_manifest(path, rows):
    fields = ["sport", "market", "mode", "weight"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_source_map_dormant_is_empty(tmp_path):
    import resolver
    man = tmp_path / "coverage_manifest.csv"
    _write_manifest(man, [{"sport": "NBA", "market": "PTS", "mode": "shadow", "weight": "0"}])
    assert resolver.source_map(manifest_path=man) == {}


def test_source_map_promoted_labels(tmp_path):
    import resolver
    man = tmp_path / "coverage_manifest.csv"
    _write_manifest(man, [
        {"sport": "NBA", "market": "PTS", "mode": "blend", "weight": "0.3"},
        {"sport": "NBA", "market": "AST", "mode": "live", "weight": "1.0"},
    ])
    sm = resolver.source_map(manifest_path=man)
    assert sm[("NBA", "PTS")] == "blend:0.300"
    assert sm[("NBA", "AST")] == "edgemodel"


# ── primary writer emits provenance ─────────────────────────────────────────

def _sample_prop():
    return {
        "player": "Anthony Edwards", "team_abbrev": "MIN", "stat": "PTS",
        "line": 27.5, "direction": "over", "proj": 30.1, "win_prob": 0.60,
        "adj_edge": 0.08, "odds": -110, "book": "draftkings", "tier": "T2",
        "pick_score": 80.0, "size": 1.5, "game": "MIN @ DEN", "sport": "NBA",
        "is_home": "False", "over_p_raw": 0.5123,
    }


def test_log_picks_emits_source_and_run_id(tmp_path, monkeypatch):
    import resolver
    import run_picks
    monkeypatch.setattr(resolver, "source_map", lambda *a, **k: {})  # dormant
    log_path = tmp_path / "pick_log.csv"
    run_picks.log_picks([_sample_prop()], "Default", log_path_override=log_path)
    with open(log_path, newline="", encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["source"] == "sabersim"          # live source while dormant
    assert row["model_version"] == ""
    assert row["run_id"]                          # non-blank run id stamped


def test_log_picks_emits_blend_source_when_promoted(tmp_path, monkeypatch):
    import resolver
    import run_picks
    monkeypatch.setattr(resolver, "source_map",
                        lambda *a, **k: {("NBA", "PTS"): "blend:0.300"})
    log_path = tmp_path / "pick_log.csv"
    run_picks.log_picks([_sample_prop()], "Default", log_path_override=log_path)
    with open(log_path, newline="", encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]
    assert row["source"] == "blend:0.300"
    assert row["model_version"] == "edgemodel"


# ── bet_lineage mirror ──────────────────────────────────────────────────────

def _lineage_db(tmp_path):
    db = tmp_path / "proj.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE bet_lineage (bet_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " run_id TEXT, game_date TEXT, sport TEXT, market TEXT, entity_id TEXT,"
        " source TEXT, challenger_source TEXT, blend_weight REAL,"
        " calibration_version TEXT, resolver_decision_json TEXT, created_ts TEXT)")
    conn.commit()
    conn.close()
    return db


def _pick_log(tmp_path, rows):
    p = tmp_path / "pick_log.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pls.CANONICAL_HEADER, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)
    return p


def test_bet_lineage_sync_mirrors_graded_props(tmp_path):
    import bet_lineage_sync as bls
    from name_utils import name_key
    db = _lineage_db(tmp_path)
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"},
        {"run_type": "primary", "result": "L", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "AST", "player": "Nikola Jokic", "source": "blend:0.300"},
        {"run_type": "game_line", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "MLB", "stat": "TOTAL", "player": "NYY @ BOS", "source": "sabersim"},  # skipped
        {"run_type": "primary", "result": "", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "REB", "player": "X", "source": "sabersim"},  # ungraded -> skipped
    ])
    n, status = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 2
    assert status == "ok"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        got = {r["entity_id"]: r for r in conn.execute(
            "SELECT entity_id, source, blend_weight FROM bet_lineage")}
        assert got[name_key("Nikola Jokic")]["source"] == "blend"
        assert got[name_key("Nikola Jokic")]["blend_weight"] == 0.3
        assert got[name_key("Anthony Edwards")]["blend_weight"] == 0.0
    finally:
        conn.close()


def test_bet_lineage_sync_idempotent_per_run(tmp_path):
    import bet_lineage_sync as bls
    db = _lineage_db(tmp_path)
    rows = [{"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
             "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}]
    pl = _pick_log(tmp_path, rows)
    bls.sync_from_pick_log(pl, db_path=db)
    bls.sync_from_pick_log(pl, db_path=db)  # re-grade same run
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM bet_lineage").fetchone()[0] == 1
    finally:
        conn.close()


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


def test_bet_lineage_sync_sets_busy_timeout_pragma(tmp_path, monkeypatch):
    """H4 hardening: sync_from_pick_log() must set PRAGMA busy_timeout on its
    own connection, matching EdgeModel's own projections_db.py timeout."""
    import bet_lineage_sync as bls
    db = _lineage_db(tmp_path)
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])
    calls = []
    real_connect = sqlite3.connect

    def spy_connect(*a, **k):
        return _ExecuteSpyConn(real_connect(*a, **k), calls)

    monkeypatch.setattr(sqlite3, "connect", spy_connect)
    bls.sync_from_pick_log(pl, db_path=db)
    assert any("busy_timeout" in c.lower() for c in calls), \
        f"expected a PRAGMA busy_timeout call, got: {calls}"


def test_bet_lineage_sync_retries_on_lock_contention_then_succeeds(tmp_path, monkeypatch):
    """H5 hardening: a transient 'database is locked' error retries instead of
    giving up on the first attempt. Simulate 2 failures then a real success."""
    import bet_lineage_sync as bls
    db = _lineage_db(tmp_path)
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])
    monkeypatch.setattr(time, "sleep", lambda s: None)
    real_connect = sqlite3.connect
    attempts = {"n": 0}

    def flaky_connect(*a, **k):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(*a, **k)

    monkeypatch.setattr(sqlite3, "connect", flaky_connect)
    n, status = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 1
    assert status == "ok"
    assert attempts["n"] == 3


def test_bet_lineage_sync_gives_up_failsoft_when_always_locked(tmp_path, monkeypatch):
    """All attempts hit lock contention -> fail-soft 0, never raises."""
    import bet_lineage_sync as bls
    db = _lineage_db(tmp_path)
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def always_locked(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(sqlite3, "connect", always_locked)
    n, status = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 0
    assert status == "lock_timeout"


def test_bet_lineage_sync_non_lock_exception_fails_soft_without_retrying(tmp_path, monkeypatch):
    """A non-lock error must fail soft immediately -- only OperationalError
    gets the retry treatment."""
    import bet_lineage_sync as bls
    db = _lineage_db(tmp_path)
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])
    attempts = {"n": 0}

    def boom(*a, **k):
        attempts["n"] += 1
        raise ValueError("not a lock issue")

    monkeypatch.setattr(sqlite3, "connect", boom)
    n, status = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 0
    assert status == "error"
    assert attempts["n"] == 1


class _InsertFailConn:
    """Proxy that lets DELETE succeed but raises on the INSERT executemany
    call, to test H6's atomicity guarantee (DELETE must roll back too)."""

    def __init__(self, real_conn):
        object.__setattr__(self, "_real", real_conn)

    def executemany(self, sql, params):
        if sql.strip().upper().startswith("INSERT"):
            raise sqlite3.IntegrityError("simulated failure mid-write")
        return self._real.executemany(sql, params)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)

    def __enter__(self):
        return self._real.__enter__()

    def __exit__(self, *a):
        return self._real.__exit__(*a)


def test_bet_lineage_sync_rolls_back_delete_if_insert_fails(tmp_path, monkeypatch):
    """H6: DELETE and INSERT are one atomic unit under `with conn:` -- if the
    INSERT fails partway, the DELETE must not have taken effect either (no
    half-deleted state left behind)."""
    import bet_lineage_sync as bls
    from name_utils import name_key
    db = _lineage_db(tmp_path)
    aja = name_key("Anthony Edwards")
    # Pre-seed an existing row for run_id='r1' that a successful sync would replace.
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO bet_lineage(run_id, game_date, sport, market, entity_id, source, "
        "challenger_source, blend_weight) VALUES('r1','2026-06-25','NBA','PTS',?,'sabersim',NULL,0.0)",
        (aja,))
    conn.commit()
    conn.close()

    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])

    real_connect = sqlite3.connect

    def spy_connect(*a, **k):
        return _InsertFailConn(real_connect(*a, **k))

    monkeypatch.setattr(sqlite3, "connect", spy_connect)

    # IntegrityError isn't OperationalError, so this goes straight to the
    # generic fail-soft path (H5's retry is scoped to lock contention only).
    n, status = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 0
    assert status == "error"

    # Verify with a clean connection: the pre-existing r1 row must STILL be
    # there. If the DELETE had committed independently of the failed INSERT
    # (the pre-H6 behavior would have been ambiguous here), this row would
    # be gone.
    conn2 = sqlite3.connect(db)
    try:
        row = conn2.execute(
            "SELECT entity_id FROM bet_lineage WHERE run_id='r1'").fetchone()
        assert row is not None and row[0] == aja
    finally:
        conn2.close()


def test_bet_lineage_sync_failsoft_missing_db(tmp_path):
    import bet_lineage_sync as bls
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])
    n, status = bls.sync_from_pick_log(pl, db_path=tmp_path / "nope.db")
    assert n == 0
    assert status == "db_missing"


# ── R-FS23-01: status must distinguish "nothing to do" from "the write failed" ─

def test_bet_lineage_sync_no_graded_rows_reports_no_rows_not_error(tmp_path, monkeypatch):
    """True zero (nothing graded yet) must be distinguishable from every
    failure branch -- this is the defect the blind-success scan found: all
    five branches returned the bare int 0 and a caller reading one int could
    not tell 'ordinary' from 'broken'."""
    import bet_lineage_sync as bls
    db = _lineage_db(tmp_path)
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"},
    ])  # ungraded -> _lineage_rows() returns [] before any DB touch
    n, status = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 0
    assert status == "no_rows"


def test_bet_lineage_sync_table_missing_reports_table_missing(tmp_path):
    """EdgeModel hasn't created bet_lineage yet -- was a bare `return 0` with
    no log line at all (the only unlogged branch of the five)."""
    import bet_lineage_sync as bls
    db = tmp_path / "proj_no_table.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE unrelated (id INTEGER)")
    conn.commit()
    conn.close()
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])
    n, status = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 0
    assert status == "table_missing"
