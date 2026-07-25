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
import time
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from secrets_config import EDGEMODEL_DB_PATH
from name_utils import name_key
from calibrated import PLATT_FIT_DATE
# Reuse the adapter's column maps so the SaberSim markets stay in lockstep with the
# EdgeModel side (same stat codes the contract holds for source='edgemodel').
from edgemodel_adapter import _BASKETBALL_COLS, _MLB_PITCHER_COLS, _MLB_BATTER_COLS

log = logging.getLogger("jonnyparlay")

_MAX_RETRIES = 3       # H5: total attempts on lock contention (busy_timeout already covers waiting within one)
_RETRY_BACKOFF_S = 2   # base backoff between attempts; multiplied by attempt number

_HOOP_MARKETS = list(_BASKETBALL_COLS.values())      # PTS REB AST 3PM
_PITCHER_MARKETS = list(_MLB_PITCHER_COLS.values())  # K OUTS ER HA BB
_BATTER_MARKETS = list(_MLB_BATTER_COLS.values())    # HITS TB HR


def _sabersim_calibration(sport: str) -> tuple:
    """The calibration regime GOVERNING this SaberSim source's downstream probabilities
    (contract governance metadata, #3). NBA/WNBA props are Platt-calibrated; MLB props
    SKIP Platt (prob_core.py) -> governed by 'none' (raw, then market shrinkage). This is
    why a single forced method would be wrong: the SaberSim path is already well-calibrated
    (brief: -0.1pp) and only some markets carry Platt."""
    if (sport or "").upper() in ("NBA", "WNBA"):
        return ("platt", PLATT_FIT_DATE)
    return ("none", None)


# Raw SQL (not EdgeModel's upsert_projection_contract) on purpose: importing
# EdgeModel's projections_db cross-repo collides on the shared `paths` module name.
# Only the contract's identity (the UNIQUE conflict key) is replicated here.
# Two variants: the shared DB may predate the calibration_method column (EdgeModel owns
# that additive migration) -> stay column-tolerant and fall back to the base upsert.
_UPSERT = (
    "INSERT INTO projection(run_id, game_date, sport, entity_type, entity_id, "
    "market, source, model_version, mean) "
    "VALUES(:run_id,:game_date,:sport,'player',:entity_id,:market,'sabersim',"
    "'sabersim',:mean) "
    "ON CONFLICT(run_id, sport, market, entity_id, source) DO UPDATE SET "
    "mean=excluded.mean, game_date=excluded.game_date, model_version=excluded.model_version"
)
_UPSERT_CAL = (
    "INSERT INTO projection(run_id, game_date, sport, entity_type, entity_id, "
    "market, source, model_version, mean, calibration_method, calibration_version) "
    "VALUES(:run_id,:game_date,:sport,'player',:entity_id,:market,'sabersim',"
    "'sabersim',:mean,:calibration_method,:calibration_version) "
    "ON CONFLICT(run_id, sport, market, entity_id, source) DO UPDATE SET "
    "mean=excluded.mean, game_date=excluded.game_date, model_version=excluded.model_version, "
    "calibration_method=excluded.calibration_method, "
    "calibration_version=excluded.calibration_version"
)


def _has_cal_col(conn) -> bool:
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(projection)")}
    except sqlite3.OperationalError:
        return False
    return "calibration_method" in cols

# #4 feed split: the SLATE (who is playing / for whom / salary), decoupled from the
# projection rows but written from the same feed. source='sabersim'.
_SLATE_UPSERT = (
    "INSERT INTO slate(game_date, sport, entity_id, name, team, opponent, position, "
    "salary, source) "
    "VALUES(:game_date,:sport,:entity_id,:name,:team,:opponent,:position,:salary,'sabersim') "
    "ON CONFLICT(game_date, sport, entity_id, source) DO UPDATE SET "
    "name=excluded.name, team=excluded.team, opponent=excluded.opponent, "
    "position=excluded.position, salary=excluded.salary"
)


def _markets_for(sport: str, player: dict) -> list:
    s = (sport or "").upper()
    if s in ("WNBA", "NBA"):
        return _HOOP_MARKETS
    if s == "MLB":
        return _PITCHER_MARKETS if player.get("is_pitcher") else _BATTER_MARKETS
    return []


def _table_exists(conn, name: str = "projection") -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def ingest_players(conn, players: list, sport: str, game_date: str, cal_col: bool = True) -> int:
    """Upsert one sport's SaberSim players into the contract. Caller commits. `cal_col`
    selects the upsert variant that also stamps calibration governance metadata (#3);
    pass False when the shared DB predates the calibration_method column."""
    run_id = f"sabersim|{(sport or '').upper()}|{game_date}"
    cal_method, cal_version = _sabersim_calibration(sport)
    sql = _UPSERT_CAL if cal_col else _UPSERT
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
            params = {
                "run_id": run_id, "game_date": game_date, "sport": (sport or "").upper(),
                "entity_id": nk, "market": mkt, "mean": mean}
            if cal_col:
                params["calibration_method"] = cal_method
                params["calibration_version"] = cal_version
            conn.execute(sql, params)
            n += 1
    return n


def write_slate(conn, players: list, sport: str, game_date: str) -> int:
    """Upsert one sport's slate rows (who is playing / team / opp / salary). Caller
    commits. The decoupled market-data record (#4), written from the same feed."""
    n = 0
    for p in players or []:
        nk = (p.get("name_key") or name_key(p.get("name", "")) or "").strip()
        if not nk:
            continue
        sal = p.get("salary")
        try:
            sal = float(sal) if sal is not None else None
        except (TypeError, ValueError):
            sal = None
        conn.execute(_SLATE_UPSERT, {
            "game_date": game_date, "sport": (sport or "").upper(), "entity_id": nk,
            "name": p.get("name"), "team": p.get("team"), "opponent": p.get("opp"),
            "position": p.get("pos"), "salary": sal})
        n += 1
    return n


def ingest(all_players: dict, game_date: str, db_path=None) -> int:
    """Write every sport's SaberSim projections (and the decoupled slate rows) into the
    shared store. `all_players` is {sport: [player dicts]} (run_picks' pool). Returns
    projection rows written (0 on any failure -- fail-soft, never raises)."""
    path = Path(db_path or EDGEMODEL_DB_PATH)
    if not path.exists():
        log.warning("sabersim_ingest: projections.db not found at %s", path)
        return 0
    for attempt in range(_MAX_RETRIES):
        try:
            conn = sqlite3.connect(path)
            conn.execute("PRAGMA busy_timeout=60000")  # match EdgeModel's own timeout (projections_db.py)
            try:
                if not _table_exists(conn, "projection"):
                    return 0  # EdgeModel hasn't created the contract yet -> skip this run
                has_slate = _table_exists(conn, "slate")
                cal_col = _has_cal_col(conn)
                total = 0
                for sport, players in (all_players or {}).items():
                    total += ingest_players(conn, players, sport, game_date, cal_col=cal_col)
                    if has_slate:
                        write_slate(conn, players, sport, game_date)
                # Nothing is committed before this point (see H5 note below) --
                # a mid-loop OperationalError means retrying from a fresh
                # connection is safe, no partial-commit double-write risk.
                conn.commit()
                return total
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            if attempt == _MAX_RETRIES - 1:
                log.warning("sabersim_ingest: write failed after %d attempts (%s)", _MAX_RETRIES, exc)
                return 0
            log.warning("sabersim_ingest: lock contention, retrying (%d/%d)", attempt + 1, _MAX_RETRIES)
            time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
        except Exception as exc:
            log.warning("sabersim_ingest: write failed (%s)", exc)
            return 0
    # Unreachable: every loop iteration returns, either on success, on the
    # final OperationalError attempt, or on any other exception. Kept only
    # so the function has an explicit fallthrough return for readability.
    return 0  # pragma: no cover
