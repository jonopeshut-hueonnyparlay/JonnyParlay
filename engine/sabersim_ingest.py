"""sabersim_ingest.py -- write the SaberSim slate's per-market projections into the
shared `projection` contract table (source='sabersim').

The unification's champion/challenger store: EdgeModel writes source='edgemodel'
(EdgeModel.populate_projection_contract); this writes the LIVE source's same-slate
numbers as source='sabersim', so both sit in one source-tagged, directly comparable
table keyed by (run_id, sport, market, entity_id, source).

Comparable markets only -- exactly the stat codes the EdgeModel adapter reads
(PTS/REB/AST/3PM; pitcher K/OUTS/ER/HA/BB; batter HITS/TB/HR) -- so a contract query
filtered to one (sport, market, entity_id) returns both sources' means side by side.

entity_id = name_key (the common cross-source key; SaberSim has no player_id).
Idempotent per slate: run_id='sabersim|<sport>|<date>' -> re-ingest upserts in place.

Fail-soft: any missing-DB / absent-table / bad-row error yields 0 rows and never
raises -- ingestion must never block pricing or grading. projections.db is the SHARED
store; writing source-tagged challenger rows is the intended ingestion path (Brief-1),
not a producer/consumer-boundary violation (the EdgeModel read side stays read-only).
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from secrets_config import EDGEMODEL_DB_PATH
from name_utils import name_key
# Reuse the adapter's column maps so the SaberSim markets stay in lockstep with the
# EdgeModel side (same stat codes the contract holds for source='edgemodel').
from edgemodel_adapter import _BASKETBALL_COLS, _MLB_PITCHER_COLS, _MLB_BATTER_COLS

log = logging.getLogger("jonnyparlay")

_HOOP_MARKETS = list(_BASKETBALL_COLS.values())      # PTS REB AST 3PM
_PITCHER_MARKETS = list(_MLB_PITCHER_COLS.values())  # K OUTS ER HA BB
_BATTER_MARKETS = list(_MLB_BATTER_COLS.values())    # HITS TB HR

# Raw SQL (not EdgeModel's upsert_projection_contract) on purpose: importing
# EdgeModel's projections_db cross-repo collides on the shared `paths` module name.
# Only the contract's identity (the UNIQUE conflict key) is replicated here.
_UPSERT = (
    "INSERT INTO projection(run_id, game_date, sport, entity_type, entity_id, "
    "market, source, model_version, mean) "
    "VALUES(:run_id,:game_date,:sport,'player',:entity_id,:market,'sabersim',"
    "'sabersim',:mean) "
    "ON CONFLICT(run_id, sport, market, entity_id, source) DO UPDATE SET "
    "mean=excluded.mean, game_date=excluded.game_date, model_version=excluded.model_version"
)


def _markets_for(sport: str, player: dict) -> list:
    s = (sport or "").upper()
    if s in ("WNBA", "NBA"):
        return _HOOP_MARKETS
    if s == "MLB":
        return _PITCHER_MARKETS if player.get("is_pitcher") else _BATTER_MARKETS
    return []


def _table_exists(conn) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='projection'"
    ).fetchone() is not None


def ingest_players(conn, players: list, sport: str, game_date: str) -> int:
    """Upsert one sport's SaberSim players into the contract. Caller commits."""
    run_id = f"sabersim|{(sport or '').upper()}|{game_date}"
    n = 0
    for p in players or []:
        nk = (p.get("name_key") or name_key(p.get("name", "")) or "").strip()
        if not nk:
            continue
        for mkt in _markets_for(sport, p):
            v = p.get(mkt)
            if v is None:
                continue
            try:
                mean = float(v)
            except (TypeError, ValueError):
                continue
            conn.execute(_UPSERT, {
                "run_id": run_id, "game_date": game_date, "sport": (sport or "").upper(),
                "entity_id": nk, "market": mkt, "mean": mean})
            n += 1
    return n


def ingest(all_players: dict, game_date: str, db_path=None) -> int:
    """Write every sport's SaberSim projections into the contract. `all_players` is
    {sport: [player dicts]} (run_picks' pool). Returns rows written (0 on any failure
    -- fail-soft, never raises)."""
    path = Path(db_path or EDGEMODEL_DB_PATH)
    if not path.exists():
        log.warning("sabersim_ingest: projections.db not found at %s", path)
        return 0
    try:
        conn = sqlite3.connect(path)
        try:
            if not _table_exists(conn):
                return 0  # EdgeModel hasn't created the contract yet -> skip this run
            total = 0
            for sport, players in (all_players or {}).items():
                total += ingest_players(conn, players, sport, game_date)
            conn.commit()
            return total
        finally:
            conn.close()
    except Exception as exc:
        log.warning("sabersim_ingest: write failed (%s)", exc)
        return 0
