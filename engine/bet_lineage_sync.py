"""bet_lineage_sync.py -- mirror graded pick provenance into projections.db.bet_lineage.

The pick_log v5 columns (source / model_version / run_id) carry per-bet provenance on
the JonnyParlay side. This denormalizes the graded single-player rows into the
EdgeModel-side `bet_lineage` table (run_id, sport, market, entity_id, source,
challenger_source, blend_weight) so source performance is reconstructable from the
shared store without reading the CSV -- the retrospective companion to the live
`projection` contract.

Idempotent: re-grading a run rewrites that run's lineage (DELETE the run_ids being
written, then INSERT). Fail-soft: any missing-DB / absent-table / bad-row error yields
0 rows and never raises -- lineage sync must never affect grading.

Only single-player prop rows (run_type in primary/bonus/calibration) are mirrored;
parlay/game-line aggregate rows have no single entity_id.
"""
from __future__ import annotations

import csv
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

log = logging.getLogger("jonnyparlay")

_MAX_RETRIES = 3       # H5: total attempts on lock contention (busy_timeout already covers waiting within one)
_RETRY_BACKOFF_S = 2   # base backoff between attempts; multiplied by attempt number

_PROP_RUN_TYPES = {"primary", "bonus", "calibration"}
_GRADED = {"W", "L", "PUSH", "P", "VOID"}


def _blend_weight(source: str) -> float:
    """Recover the EdgeModel blend weight from a v5 source label."""
    s = (source or "").strip().lower()
    if s == "edgemodel":
        return 1.0
    if s.startswith("blend:"):
        try:
            return max(0.0, min(1.0, float(s.split(":", 1)[1])))
        except (TypeError, ValueError):
            return 0.0
    return 0.0  # live source (sabersim) -> no EdgeModel contribution


def _base_source(source: str) -> str:
    s = (source or "").strip().lower()
    return "blend" if s.startswith("blend:") else (s or "sabersim")


def _lineage_rows(pick_log_path: Path) -> list[dict]:
    """Read graded single-player prop rows -> bet_lineage row dicts."""
    if not pick_log_path.exists():
        return []
    out: list[dict] = []
    with open(pick_log_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f):
            if (r.get("run_type") or "").strip().lower() not in _PROP_RUN_TYPES:
                continue
            if (r.get("result") or "").strip().upper() not in _GRADED:
                continue
            run_id = (r.get("run_id") or "").strip()
            entity = name_key(r.get("player", ""))
            if not run_id or not entity:
                continue
            src = r.get("source") or "sabersim"
            out.append({
                "run_id": run_id,
                "game_date": (r.get("date") or "").strip(),
                "sport": (r.get("sport") or "").strip().upper(),
                "market": (r.get("stat") or "").strip().upper(),
                "entity_id": entity,
                "source": _base_source(src),
                "challenger_source": "edgemodel",
                "blend_weight": _blend_weight(src),
            })
    return out


def sync_from_pick_log(pick_log_path, db_path=None) -> int:
    """Mirror graded prop provenance into bet_lineage. Returns rows written (0 on any
    failure -- fail-soft). Idempotent per run_id."""
    rows = _lineage_rows(Path(pick_log_path))
    if not rows:
        return 0
    path = Path(db_path or EDGEMODEL_DB_PATH)
    if not path.exists():
        log.warning("bet_lineage_sync: projections.db not found at %s", path)
        return 0
    for attempt in range(_MAX_RETRIES):
        try:
            conn = sqlite3.connect(path)
            conn.execute("PRAGMA busy_timeout=60000")  # match EdgeModel's own timeout (projections_db.py)
            try:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                                "name='bet_lineage'").fetchone() is None:
                    return 0  # EdgeModel hasn't created the table yet -> skip
                run_ids = sorted({r["run_id"] for r in rows})
                # H6: explicit `with conn:` -- Python's sqlite3 module commits
                # on clean exit and rolls back on any exception raised inside,
                # making the DELETE+INSERT atomicity a guarantee of this code
                # rather than an accident of sqlite3's default isolation_level
                # (which happened to already commit them together, but nothing
                # here previously said so). Also gives H5's retry-from-fresh-
                # connection reasoning an explicit backstop: even if a future
                # change adds a commit-worthy statement before this block, a
                # mid-block failure still can't leave a half-applied write.
                with conn:
                    conn.executemany("DELETE FROM bet_lineage WHERE run_id = ?",
                                     [(rid,) for rid in run_ids])
                    conn.executemany(
                        "INSERT INTO bet_lineage(run_id, game_date, sport, market, entity_id, "
                        "source, challenger_source, blend_weight) "
                        "VALUES(:run_id,:game_date,:sport,:market,:entity_id,:source,"
                        ":challenger_source,:blend_weight)", rows)
                return len(rows)
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            if attempt == _MAX_RETRIES - 1:
                log.warning("bet_lineage_sync: write failed after %d attempts (%s)", _MAX_RETRIES, exc)
                return 0
            log.warning("bet_lineage_sync: lock contention, retrying (%d/%d)", attempt + 1, _MAX_RETRIES)
            time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
        except Exception as exc:
            log.warning("bet_lineage_sync: write failed (%s)", exc)
            return 0
    # Unreachable: every loop iteration returns, either on success, on the
    # final OperationalError attempt, or on any other exception. Kept only
    # so the function has an explicit fallthrough return for readability.
    return 0  # pragma: no cover
