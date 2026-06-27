"""Tests for pick_log v5 -- per-bet source provenance (source/model_version/run_id).

Covers the schema bump (append-only, blank-fill migration), the resolver source
decision, the primary writer emitting provenance, and the bet_lineage mirror.
"""
import csv
import sqlite3

import pick_log_schema as pls


# ── schema (v5, append-only) ────────────────────────────────────────────────

def test_schema_version_and_header():
    assert pls.SCHEMA_VERSION == 5
    assert pls.CANONICAL_HEADER[-3:] == ["source", "model_version", "run_id"]
    assert pls.LIVE_SOURCE == "sabersim"


def test_detect_v5_and_v4():
    assert pls.detect_schema_version(pls.CANONICAL_HEADER) == 5
    v4 = [c for c in pls.CANONICAL_HEADER if c not in ("source", "model_version", "run_id")]
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
    n = bls.sync_from_pick_log(pl, db_path=db)
    assert n == 2
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


def test_bet_lineage_sync_failsoft_missing_db(tmp_path):
    import bet_lineage_sync as bls
    pl = _pick_log(tmp_path, [
        {"run_type": "primary", "result": "W", "run_id": "r1", "date": "2026-06-26",
         "sport": "NBA", "stat": "PTS", "player": "Anthony Edwards", "source": "sabersim"}])
    assert bls.sync_from_pick_log(pl, db_path=tmp_path / "nope.db") == 0
