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


def fetch(sport: str, game_date: str, db_path=None) -> dict:
    """{(name_key, stat): proj_value} of EdgeModel projections for a sport+date.

    Returns {} on any failure (unknown sport, missing DB/date, absent table).
    """
    specs = _SOURCES.get((sport or "").upper())
    if not specs:
        return {}
    path = Path(db_path or EDGEMODEL_DB_PATH)
    if not path.exists():
        log.warning("edgemodel_adapter: projections.db not found at %s", path)
        return {}

    out: dict = {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
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
        finally:
            conn.close()
    except Exception as exc:
        log.warning("edgemodel_adapter: read failed (%s)", exc)
        return {}
    return out
