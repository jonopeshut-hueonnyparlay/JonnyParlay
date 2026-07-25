"""edgemodel_adapter.py -- read EdgeModel projections from projections.db.

The unification's EdgeModelAdapter: lets JonnyParlay line EdgeModel's (currently
orphaned) projections.db output up against the live source per market, for the
champion/challenger source-comparison shadow (measure EdgeModel vs SaberSim on
identical markets/outcomes -> per-market readiness to take over).

Read-only (opens the DB ?mode=ro); resolves the path via EDGEMODEL_DB_PATH;
returns {} on ANY failure (missing DB / date / table / column) so callers never
break. `fetch(sport, game_date)` -> {(name_key, stat): proj_value} where stat is
the JonnyParlay stat code (PTS/REB/AST/3PM; K/OUTS/ER/HA/BB; HITS/TB/HR), so it
compares directly to pick_log / the live CSV.

This is read-side only: nothing here writes to projections.db (the producer/
consumer boundary stays intact).
"""
import logging
import sqlite3
from pathlib import Path

from secrets_config import EDGEMODEL_DB_PATH
from name_utils import name_key

log = logging.getLogger("jonnyparlay")

# projections.db column -> JonnyParlay stat code, per source table.
_BASKETBALL_COLS = {"proj_pts": "PTS", "proj_reb": "REB", "proj_ast": "AST", "proj_fg3m": "3PM"}
_MLB_PITCHER_COLS = {"proj_k": "K", "proj_outs": "OUTS", "proj_er": "ER", "proj_ha": "HA", "proj_bb": "BB"}
_MLB_BATTER_COLS = {"proj_hits": "HITS", "proj_tb": "TB", "proj_hr": "HR"}

# sport -> [(table, name_column, sport_filter_or_None, column_map), ...]
_SOURCES = {
    "WNBA": [("projections", "player_name", "WNBA", _BASKETBALL_COLS)],
    "NBA":  [("projections", "player_name", "NBA", _BASKETBALL_COLS)],
    "MLB":  [("mlb_pitcher_projections", "pitcher_name", None, _MLB_PITCHER_COLS),
             ("mlb_batter_projections", "batter_name", None, _MLB_BATTER_COLS)],
}


def _fetch_from_contract(conn, sport: str, game_date: str) -> dict:
    """Read EdgeModel rows from the source-tagged `projection` contract table.

    The contract stores entity_id=name_key and market already in JonnyParlay stat
    codes (PTS/REB/.../HITS/TB/HR) with mean=the projection -- i.e. the exact same
    numbers the per-sport tables hold, written by EdgeModel's
    populate_projection_contract. Returns {} if the table is absent (fail-soft) or
    no row matches (then the caller falls back to the per-sport tables, byte-identically).
    """
    out: dict = {}
    try:
        rows = conn.execute(
            "SELECT entity_id, market, mean FROM projection "
            "WHERE game_date = ? AND upper(sport) = ? AND source = 'edgemodel' "
            "AND mean IS NOT NULL",
            [game_date, (sport or "").upper()],
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # ADR-005 / 1A (revised per architecture review): this already fails soft
        # (falls back to the per-sport tables below) -- that's correct and
        # unchanged. What was missing was observability: "no such table"
        # (EdgeModel hasn't created the contract yet -- expected, benign
        # pre-first-run) and "no such column" (the contract's actual shape
        # changed -- worth investigating) were both silently indistinguishable
        # as a bare `{}`.
        if "no such table" in str(exc):
            log.debug("edgemodel_adapter: contract table not yet present (%s)", exc)
        else:
            log.warning("edgemodel_adapter: contract query failed, falling back "
                       "to per-sport tables (%s)", exc)
        return {}  # fail-soft either way -- caller falls back to per-sport tables
    for r in rows:
        nk = (r["entity_id"] or "").strip()
        stat = r["market"]
        if nk and stat:
            out[(nk, stat)] = float(r["mean"])
    return out


def _fetch_from_per_sport(conn, specs, game_date: str) -> dict:
    """Read EdgeModel projections straight from the per-sport projection tables."""
    out: dict = {}
    for table, name_col, sport_filter, col_map in specs:
        select_cols = ", ".join([name_col] + list(col_map))
        where, params = "run_date = ?", [game_date]
        if sport_filter is not None:
            where += " AND sport = ?"
            params.append(sport_filter)
        try:
            rows = conn.execute(
                f"SELECT {select_cols} FROM {table} WHERE {where}", params
            ).fetchall()
        except sqlite3.OperationalError:
            continue  # table/column absent in this DB -> skip, fail-soft
        for r in rows:
            nk = name_key(r[name_col])
            if not nk:
                continue
            for db_col, stat in col_map.items():
                v = r[db_col]
                if v is not None:
                    out[(nk, stat)] = float(v)
    return out


def fetch(sport: str, game_date: str, db_path=None) -> dict:
    """{(name_key, stat): proj_value} of EdgeModel projections for a sport+date.

    Reads the source-tagged `projection` contract first (the unification backbone);
    falls back to the per-sport projection tables when the contract has no row for
    this slate (historical dates, or before EdgeModel's first contract-populating
    run). The two paths are byte-identical -- the contract's mean is written from the
    same per-sport numbers -- so switching the reader changes nothing downstream.

    Returns {} on any failure (unknown sport, missing DB/date, absent tables).
    """
    specs = _SOURCES.get((sport or "").upper())
    if not specs:
        return {}
    path = Path(db_path or EDGEMODEL_DB_PATH)
    if not path.exists():
        log.warning("edgemodel_adapter: projections.db not found at %s", path)
        return {}

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            out = _fetch_from_contract(conn, sport, game_date)
            if out:
                return out
            return _fetch_from_per_sport(conn, specs, game_date)
        finally:
            conn.close()
    except Exception as exc:
        log.warning("edgemodel_adapter: read failed (%s)", exc)
        return {}
