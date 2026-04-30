"""engine/projections_db.py -- SQLite backing store for the custom projection engine.

Step 1 of the build plan (see ``memory/projects/custom-projection-engine.md``).
This module owns schema creation, the historical NBA pull, and the idempotent
upserts used by the daily incremental refresh. Downstream modules
(``nba_projector.py``, ``nhl_projector.py``, ``mlb_projector.py``, and
``injury_parser.py``) read from these tables to compute EWMA rates,
opponent/pace adjustments, and minutes redistributions.

Design notes
------------
* One DB, one ``data/projections.db`` file, living next to ``pick_log.csv``.
  Resolved via :mod:`engine.paths` so ``JONNYPARLAY_ROOT`` works the same way
  here as it does for the rest of the engine.
* ``player_game_logs`` is **sport-agnostic** -- every sport writes to the same
  table with a ``sport`` discriminator, so the projector code can share EWMA
  machinery. Unused columns for a given sport stay NULL.
* ``player_index`` is keyed on :func:`engine.name_utils.fold_name` so cross-
  source joins (nba_api <-> Odds API <-> SaberSim <-> pick_log) go through the
  same contract as the rest of the engine.
* All writes are **idempotent**. Daily incremental runs just re-run the pull;
  ``INSERT OR REPLACE`` keeps the latest copy.
* No external projections engine writes here from Windows; the DB is safe to
  rebuild under Cowork without coordinating with the live daily workflow.

Bootstrap
---------
    python engine/projections_db.py --init                      # create schema
    python engine/projections_db.py --pull-nba                  # last 3 seasons
    python engine/projections_db.py --pull-nba --seasons 2025-26  # targeted
    python engine/projections_db.py --verify                    # sanity stats

The historical pull uses the nba_api ``PlayerGameLogs`` endpoint -- one HTTP
call per season (bulk) -- plus ``CommonAllPlayers`` for the player index.
No per-player round-trips on the initial pull.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

# Engine imports -- stay consistent with the rest of the codebase. ``paths``
# resolves the repo root (honoring ``$JONNYPARLAY_ROOT`` under Cowork) and
# ``name_utils.fold_name`` is the single canonical folding contract for any
# cross-source player name comparison.
try:
    from engine import paths  # when imported as ``engine.projections_db``
    from engine.name_utils import fold_name
except ImportError:  # pragma: no cover -- running as a script from engine/
    import paths  # type: ignore
    from name_utils import fold_name  # type: ignore


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_FILENAME = "projections.db"
DB_PATH: Path = paths.data_path(DB_FILENAME)

# Three-season rolling window for the initial bootstrap. More than 3 seasons
# hurts the EWMA signal (rookies, role changes, rule tweaks) and inflates the
# DB without proportional accuracy gains.
CURRENT_SEASON = "2025-26"
DEFAULT_HISTORICAL_SEASONS: tuple[str, ...] = ("2023-24", "2024-25", "2025-26")

# Polite pause between nba_api requests. PlayerGameLogs is a bulk endpoint
# (one call per season), so this mainly matters when we add CommonAllPlayers
# and any per-player fallbacks. stats.nba.com throttles aggressively; 1.0s
# is the conventional safe floor.
NBA_API_SLEEP_SEC = 1.0

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Schema matches the spec in ``memory/projects/custom-projection-engine.md``.
# Sport-specific columns live alongside each other; rows from other sports
# leave them NULL. This keeps the EWMA logic in the projector modules generic.
_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS player_game_logs (
        player_id    TEXT NOT NULL,
        player_name  TEXT NOT NULL,
        sport        TEXT NOT NULL,
        game_date    TEXT NOT NULL,
        opponent     TEXT,
        home_away    TEXT,        -- 'home' | 'away'
        minutes      REAL,
        -- NBA
        pts          REAL,
        reb          REAL,
        ast          REAL,
        tpm          REAL,
        -- NHL
        sog          REAL,
        a_nhl        REAL,
        -- MLB (hitter + pitcher stats live in same table)
        hits         REAL,
        k            REAL,
        bb           REAL,
        ip           REAL,
        er           REAL,
        pa           REAL,
        r            REAL,
        rbi          REAL,
        hr           REAL,
        PRIMARY KEY (player_id, game_date, sport)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS team_defense (
        team              TEXT NOT NULL,
        sport             TEXT NOT NULL,
        position          TEXT NOT NULL,
        stat              TEXT NOT NULL,
        allowed_rate      REAL,
        league_avg_rate   REAL,
        last_updated      TEXT,
        PRIMARY KEY (team, sport, position, stat)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pace_factors (
        team              TEXT NOT NULL,
        sport             TEXT NOT NULL,
        game_date         TEXT NOT NULL,
        implied_total     REAL,
        league_avg_total  REAL,
        PRIMARY KEY (team, sport, game_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS injury_status (
        player_name   TEXT NOT NULL,
        team          TEXT,
        sport         TEXT NOT NULL,
        game_date     TEXT NOT NULL,
        status        TEXT,       -- OUT | QUESTIONABLE | PROBABLE | DOUBTFUL | ACTIVE
        reason        TEXT,
        snapshot_time TEXT,
        PRIMARY KEY (player_name, team, game_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS player_index (
        fold_name      TEXT PRIMARY KEY,
        nba_api_id     TEXT,
        nhl_api_id     TEXT,
        mlb_api_id     TEXT,
        display_name   TEXT,
        team           TEXT,
        position       TEXT
    )
    """,
]

# Auxiliary indexes -- the projector queries by (player_id, sport) ordered by
# date descending when building EWMA windows, and by (game_date, sport) when
# computing matchup factors. Primary keys cover equality lookups; these two
# cover the range-scan hot paths.
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_game_logs_sport_date ON player_game_logs(sport, game_date)",
    "CREATE INDEX IF NOT EXISTS idx_game_logs_player_sport_date ON player_game_logs(player_id, sport, game_date)",
    "CREATE INDEX IF NOT EXISTS idx_injury_sport_date ON injury_status(sport, game_date)",
    "CREATE INDEX IF NOT EXISTS idx_player_index_nba ON player_index(nba_api_id)",
]


# ---------------------------------------------------------------------------
# Connection + schema init
# ---------------------------------------------------------------------------

def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Return a connection to the projections DB.

    The DB file is created lazily on first connect. The parent directory
    (``data/``) is guaranteed by ``paths`` but we create it defensively here
    so a fresh checkout without an existing data dir still works.
    """
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # Foreign keys aren't used (all relationships are informal) but enabling
    # keeps behavior consistent if we add them later. WAL journaling gives
    # the projector safer concurrent reads while the injury_parser writes.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> Path:
    """Create all tables and indexes. Idempotent -- safe to call repeatedly.

    Returns the path to the DB file for logging/verification.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    # Recover the actual on-disk filename from the connection so the log
    # line is accurate when a caller passes a custom path (tests, Cowork
    # scratch runs). ``PRAGMA database_list`` returns rows of
    # ``(seq, name, file)`` for each attached DB; ``main`` is the one we
    # opened.
    try:
        db_file = Path(next(
            (r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"),
            str(DB_PATH),
        ))
        with conn:  # transactional
            for stmt in _SCHEMA:
                conn.execute(stmt)
            for stmt in _INDEXES:
                conn.execute(stmt)
        logger.info("projections.db schema initialized at %s", db_file)
        return db_file
    finally:
        if own_conn:
            conn.close()


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_matchup(matchup: str) -> tuple[str, str]:
    """Split an nba_api ``MATCHUP`` string into ``(opponent, home_away)``.

    Examples::

        "LAL vs. BOS" -> ("BOS", "home")
        "LAL @ BOS"   -> ("BOS", "away")
    """
    if not matchup:
        return ("", "")
    s = matchup.strip()
    # ``vs.`` is home, ``@`` is away -- per the stats.nba.com convention.
    if " vs. " in s:
        _, opp = s.split(" vs. ", 1)
        return (opp.strip(), "home")
    if " vs " in s:  # defensive -- some older payloads omit the period
        _, opp = s.split(" vs ", 1)
        return (opp.strip(), "home")
    if " @ " in s:
        _, opp = s.split(" @ ", 1)
        return (opp.strip(), "away")
    return ("", "")


def _parse_minutes(val) -> float | None:
    """Coerce an nba_api ``MIN`` value into a float.

    PlayerGameLogs returns numeric values but the exact shape varies by
    endpoint/version -- float, int-string, or the old ``MM:SS`` form. Accept
    all three and return ``None`` on anything we can't parse.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    if ":" in s:
        try:
            mm, ss = s.split(":", 1)
            return float(mm) + float(ss) / 60.0
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_game_date(val) -> str:
    """Normalize an nba_api game date into ``YYYY-MM-DD``.

    nba_api typically returns ``"2026-04-14T00:00:00"`` or ``"2026-04-14"``
    depending on endpoint. Both trim cleanly to the first 10 chars, but we
    fall through ``datetime.fromisoformat`` for anything unexpected.
    """
    if not val:
        return ""
    s = str(val).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    try:
        return datetime.fromisoformat(s).strftime("%Y-%m-%d")
    except ValueError:
        return s  # last-ditch: store as-is so the bug is visible downstream


def _as_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _canonical_position(pos: str) -> str:
    """Collapse a raw POSITION string into one of ``"G"`` / ``"F"`` / ``"C"``.

    Handles both abbreviated tokens from CommonTeamRoster (``"G"``,
    ``"G-F"``, ``"F-C"``, ``"C"``) and expanded tokens from
    CommonPlayerInfo (``"Guard"``, ``"Forward-Center"``).  Takes the
    primary (leftmost) position when dual-position tokens are present.
    Returns ``""`` for empty or unrecognised inputs -- callers treat that
    as position-unknown rather than propagating a bad value.

    This mirrors :func:`engine.backtest_slice._collapse_position` which
    serves the same normalisation for the diagnostic reporting path.

    # [H2'-PREREQ1] Canonical 3-bucket mapping required by role-tier
    # classifier (H2') and per-position Bayesian shrinkage (H6').
    # Expanding to 5 buckets (PG/SG/SF/PF/C) is deferred to H2' itself,
    # which needs height/wingspan data for the full position-tier split.
    """
    if not pos:
        return ""
    p = pos.upper().strip()
    primary = p.split("-")[0].split("/")[0].strip()
    if primary in ("G", "PG", "SG", "GUARD"):
        return "G"
    if primary in ("F", "SF", "PF", "FORWARD"):
        return "F"
    if primary in ("C", "CENTER"):
        return "C"
    return ""


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

_NBA_COLS = (
    "player_id", "player_name", "sport",
    "game_date", "opponent", "home_away",
    "minutes", "pts", "reb", "ast", "tpm",
)


def upsert_nba_game_logs(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    """Insert NBA game-log rows. ``INSERT OR REPLACE`` -- idempotent.

    Returns the number of rows written. ``rows`` should be the dicts emitted
    by :func:`pull_nba_season` (one row per player/game).
    """
    sql = (
        "INSERT OR REPLACE INTO player_game_logs "
        f"({', '.join(_NBA_COLS)}) "
        f"VALUES ({', '.join('?' * len(_NBA_COLS))})"
    )
    params = [tuple(r.get(c) for c in _NBA_COLS) for r in rows]
    if not params:
        return 0
    with conn:
        conn.executemany(sql, params)
    return len(params)


def upsert_player_index(
    conn: sqlite3.Connection,
    folded: str,
    *,
    nba_api_id: str | None = None,
    nhl_api_id: str | None = None,
    mlb_api_id: str | None = None,
    display_name: str | None = None,
    team: str | None = None,
    position: str | None = None,
) -> None:
    """Upsert a row into ``player_index``, preserving IDs from other sports.

    If a row already exists for ``folded``, we only overwrite the fields
    that the caller actually provided -- ``COALESCE(new, existing)`` -- so
    that populating, say, the NBA ID doesn't wipe a previously-set NHL ID
    for a name collision.
    """
    if not folded:
        return
    with conn:
        conn.execute(
            """
            INSERT INTO player_index
                (fold_name, nba_api_id, nhl_api_id, mlb_api_id, display_name, team, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fold_name) DO UPDATE SET
                nba_api_id   = COALESCE(excluded.nba_api_id,   player_index.nba_api_id),
                nhl_api_id   = COALESCE(excluded.nhl_api_id,   player_index.nhl_api_id),
                mlb_api_id   = COALESCE(excluded.mlb_api_id,   player_index.mlb_api_id),
                display_name = COALESCE(excluded.display_name, player_index.display_name),
                team         = COALESCE(excluded.team,         player_index.team),
                position     = COALESCE(excluded.position,     player_index.position)
            """,
            (folded, nba_api_id, nhl_api_id, mlb_api_id, display_name, team, position),
        )


# ---------------------------------------------------------------------------
# NBA historical pull
# ---------------------------------------------------------------------------

def pull_nba_season(
    season: str,
    *,
    season_type: str = "Regular Season",
    timeout: int = 60,
) -> list[dict]:
    """Pull one full season of NBA player game logs via nba_api bulk endpoint.

    ``season`` must use the nba_api format -- e.g. ``"2025-26"``. Returns a
    list of dicts already shaped for :func:`upsert_nba_game_logs`.

    Raises the underlying ``requests`` exception on network failure; the
    caller decides whether to retry. We deliberately keep retry logic in
    :func:`pull_nba_historical` so a caller driving a single season can
    handle failures however it wants.
    """
    from nba_api.stats.endpoints import playergamelogs  # type: ignore

    logger.info("Pulling NBA %s (%s) ...", season, season_type)
    t0 = time.monotonic()
    endpoint = playergamelogs.PlayerGameLogs(
        season_nullable=season,
        season_type_nullable=season_type,
        league_id_nullable="00",
        timeout=timeout,
    )
    # nba_api's ``get_data_frames()`` assumes the legacy V2 response shape
    # with a singular ``resultSet`` key. The 2025-26 stats.nba.com endpoints
    # return a plural ``resultSets`` LIST, so that helper raises
    # ``KeyError: 'resultSet'``. Parse the raw JSON ourselves -- always index
    # ``resultSets[0]`` for PlayerGameLogs (single-table response).
    resp = endpoint.get_dict()
    result_sets = resp.get("resultSets") or []
    if not result_sets:
        logger.warning("nba_api returned no resultSets for %s", season)
        return []
    rs = result_sets[0]
    headers = rs.get("headers") or []
    raw_rows = rs.get("rowSet") or []
    logger.info(
        "  %s: %d raw rows in %.1fs",
        season, len(raw_rows), time.monotonic() - t0,
    )

    rows: list[dict] = []
    for row in raw_rows:
        rec = dict(zip(headers, row))
        matchup = rec.get("MATCHUP", "")
        opponent, home_away = _parse_matchup(matchup)
        rows.append({
            "player_id":   str(rec.get("PLAYER_ID", "")),
            "player_name": rec.get("PLAYER_NAME", ""),
            "sport":       "nba",
            "game_date":   _parse_game_date(rec.get("GAME_DATE")),
            "opponent":    opponent,
            "home_away":   home_away,
            "minutes":     _parse_minutes(rec.get("MIN")),
            "pts":         _as_float(rec.get("PTS")),
            "reb":         _as_float(rec.get("REB")),
            "ast":         _as_float(rec.get("AST")),
            "tpm":         _as_float(rec.get("FG3M")),
        })
    return rows


def pull_nba_player_index(*, timeout: int = 60) -> list[dict]:
    """Pull the active NBA player list via ``CommonAllPlayers``.

    Returns a list of ``{nba_api_id, display_name, team}`` dicts.
    Position is not populated here -- ``CommonAllPlayers`` does not
    expose it.  Call :func:`pull_nba_positions_bulk` after this to
    backfill ``player_index.position`` via ``CommonTeamRoster`` (~30
    calls, one per team).
    """
    from nba_api.stats.endpoints import commonallplayers  # type: ignore

    logger.info("Pulling NBA CommonAllPlayers index ...")
    endpoint = commonallplayers.CommonAllPlayers(
        is_only_current_season=1,
        league_id="00",
        season=CURRENT_SEASON,
        timeout=timeout,
    )
    frames = endpoint.get_data_frames()
    if not frames:
        return []
    df = frames[0]
    out: list[dict] = []
    for rec in df.to_dict(orient="records"):
        pid = rec.get("PERSON_ID")
        if pid is None:
            continue
        name = rec.get("DISPLAY_FIRST_LAST") or rec.get("DISPLAY_LAST_COMMA_FIRST") or ""
        out.append({
            "nba_api_id":   str(pid),
            "display_name": name,
            "team":         rec.get("TEAM_ABBREVIATION") or rec.get("TEAM_CODE") or "",
        })
    logger.info("  index: %d active players", len(out))
    return out


def pull_nba_positions_bulk(
    *,
    timeout: int = 60,
    sleep: float = NBA_API_SLEEP_SEC,
) -> dict[str, str]:
    """Pull position for every active NBA player via ``CommonTeamRoster``.

    Calls ``CommonTeamRoster`` once per team (~30 calls total) rather than
    ``CommonPlayerInfo`` (~500 per-player calls).  Returns a
    ``{nba_api_id_str: canonical_position}`` dict where canonical_position
    is one of ``"G"`` / ``"F"`` / ``"C"``.  Players not found on any
    roster (free agents, two-way on G-League assignment) are omitted from
    the output -- callers treat missing entries as position-unknown.

    # [H2'-PREREQ1] Position data is required by the role-tier classifier
    # (H2') for role-stratified rate subsampling, and by H6' for
    # per-position Bayesian shrinkage.  This is the lowest-cost bulk path:
    # CommonAllPlayers does not expose position; per-player CommonPlayerInfo
    # would require 500+ API round-trips at NBA rate limits.
    """
    from nba_api.stats.endpoints import commonteamroster  # type: ignore
    from nba_api.stats.static import teams as nba_teams_static  # type: ignore

    all_teams = nba_teams_static.get_teams()
    out: dict[str, str] = {}
    logger.info(
        "Pulling NBA positions via CommonTeamRoster (%d teams) ...",
        len(all_teams),
    )
    for i, team_meta in enumerate(all_teams):
        team_id = str(team_meta["id"])
        try:
            endpoint = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=CURRENT_SEASON,
                timeout=timeout,
            )
            # Use get_dict() + manual parse -- get_data_frames() raises
            # KeyError on 2025-26 endpoints that return plural resultSets
            # (same issue that required the workaround in pull_nba_season).
            resp = endpoint.get_dict()
            result_sets = resp.get("resultSets") or []
            # CommonTeamRoster response contains two result sets: "Coaches"
            # and "CommonTeamRoster".  Match by name so ordering changes
            # don't break the parse.
            rs = next(
                (rs for rs in result_sets if rs.get("name") == "CommonTeamRoster"),
                None,
            )
            if rs is None:
                logger.warning(
                    "CommonTeamRoster: no 'CommonTeamRoster' resultSet "
                    "for team_id=%s (%s)",
                    team_id, team_meta.get("abbreviation", "?"),
                )
                continue
            headers = rs.get("headers") or []
            for row in rs.get("rowSet") or []:
                rec = dict(zip(headers, row))
                pid = rec.get("PLAYER_ID")
                pos_raw = rec.get("POSITION") or ""
                if pid is not None:
                    canonical = _canonical_position(pos_raw)
                    if canonical:  # skip empty / unrecognised
                        out[str(pid)] = canonical
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "CommonTeamRoster failed for team_id=%s (%s): %s",
                team_id, team_meta.get("abbreviation", "?"), e,
            )
        if i < len(all_teams) - 1:
            time.sleep(sleep)

    logger.info("  positions: %d players mapped", len(out))
    return out


def backfill_positions(db_path: Path | str | None = None) -> int:
    """Backfill ``player_index.position`` for all NBA players.

    Calls :func:`pull_nba_positions_bulk` and writes the canonical
    position into any ``player_index`` row that has an ``nba_api_id``.
    Safe to re-run -- ``COALESCE`` logic in :func:`upsert_player_index`
    preserves existing non-NULL positions (so a prior correct manual fix
    won't be overwritten by a stale roster pull).

    Known limitation: position is derived from the *current* roster.
    After mid-season trades a player's entry reflects their new team's
    positional notation.  Tracked as a known-unknown; quarterly refresh
    via ``--backfill-positions`` is sufficient for projection accuracy.

    Returns the count of rows updated.

    # [H2'-PREREQ1] Standalone backfill lets Jono fix the existing DB
    # without re-pulling 3 seasons of game logs (~10 min).
    """
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT fold_name, nba_api_id FROM player_index "
            "WHERE nba_api_id IS NOT NULL"
        ).fetchall()
        if not rows:
            logger.info("backfill_positions: no NBA rows in player_index")
            return 0

        pos_map = pull_nba_positions_bulk()
        updated = 0
        for r in rows:
            fn  = r["fold_name"]  if hasattr(r, "keys") else r[0]
            pid = r["nba_api_id"] if hasattr(r, "keys") else r[1]
            pos = pos_map.get(str(pid))
            if pos:
                upsert_player_index(conn, fn, position=pos)
                updated += 1
        logger.info(
            "backfill_positions: %d/%d rows updated", updated, len(rows)
        )
        return updated
    finally:
        conn.close()


def pull_nba_historical(
    seasons: Iterable[str] = DEFAULT_HISTORICAL_SEASONS,
    *,
    season_type: str = "Regular Season",
    sleep: float = NBA_API_SLEEP_SEC,
    db_path: Path | str | None = None,
) -> dict[str, int]:
    """Pull the last N seasons of NBA game logs and populate the DB.

    ``seasons`` is an iterable of nba_api-formatted season strings
    (``"YYYY-YY"``). Returns a ``{season: row_count}`` dict for
    logging/verification.
    """
    conn = get_connection(db_path)
    try:
        init_db(conn)  # defensive -- harmless if already initialized
        totals: dict[str, int] = {}
        seasons = list(seasons)
        for i, season in enumerate(seasons):
            for attempt in range(3):
                try:
                    rows = pull_nba_season(season, season_type=season_type)
                    written = upsert_nba_game_logs(conn, rows)
                    totals[season] = written
                    logger.info("  %s: %d rows written", season, written)
                    break
                except Exception as e:  # noqa: BLE001
                    wait = 2 ** attempt
                    logger.warning(
                        "  %s attempt %d failed: %s; retrying in %ds",
                        season, attempt + 1, e, wait,
                    )
                    time.sleep(wait)
            else:
                logger.error("  %s: giving up after 3 attempts", season)
                totals[season] = 0
            if i < len(seasons) - 1:
                time.sleep(sleep)

        try:
            index_rows = pull_nba_player_index()
            for r in index_rows:
                upsert_player_index(
                    conn,
                    fold_name(r["display_name"]),
                    nba_api_id=r["nba_api_id"],
                    display_name=r["display_name"],
                    team=r["team"],
                )
            logger.info("  player_index: %d NBA rows upserted", len(index_rows))
            # [H2'-PREREQ1] Backfill position after player index is loaded.
            # CommonAllPlayers (used above) does not expose position; pull
            # it now via CommonTeamRoster (~30 calls) and write G/F/C into
            # player_index.position for use by the role-tier classifier (H2').
            pos_map = pull_nba_positions_bulk()
            pos_updated = 0
            for r in index_rows:
                pid = r.get("nba_api_id")
                pos = pid and pos_map.get(str(pid))
                if pos:
                    upsert_player_index(
                        conn,
                        fold_name(r["display_name"]),
                        position=pos,
                    )
                    pos_updated += 1
            logger.info(
                "  player_index: %d/%d positions backfilled",
                pos_updated, len(index_rows),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("player_index pull failed (non-fatal): %s", e)

        return totals
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(db_path: Path | str | None = None) -> dict:
    """Return a summary of DB contents for sanity checking."""
    conn = get_connection(db_path)
    try:
        out: dict = {"db_path": str(Path(db_path) if db_path else DB_PATH)}

        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
        out["tables"] = tables

        rows = conn.execute(
            "SELECT sport, COUNT(*) AS n, "
            "       MIN(game_date) AS first_date, "
            "       MAX(game_date) AS last_date, "
            "       COUNT(DISTINCT player_id) AS players "
            "FROM player_game_logs "
            "GROUP BY sport"
        ).fetchall()
        out["game_logs_by_sport"] = [dict(r) for r in rows]

        nba_by_season = conn.execute(
            "SELECT SUBSTR(game_date, 1, 4) AS year, COUNT(*) AS n "
            "FROM player_game_logs WHERE sport='nba' GROUP BY year ORDER BY year"
        ).fetchall()
        out["nba_by_year"] = [dict(r) for r in nba_by_season]

        idx_row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "       COALESCE(SUM(CASE WHEN nba_api_id IS NOT NULL THEN 1 ELSE 0 END), 0) AS nba "
            "FROM player_index"
        ).fetchone()
        out["player_index"] = dict(idx_row) if idx_row else {}

        orphans = conn.execute(
            "SELECT COUNT(DISTINCT player_name) AS n FROM player_game_logs "
            "WHERE sport='nba' AND player_name NOT IN "
            "  (SELECT display_name FROM player_index WHERE nba_api_id IS NOT NULL)"
        ).fetchone()
        out["nba_log_names_not_in_index"] = orphans["n"] if orphans else None

        return out
    finally:
        conn.close()


def _format_verify(summary: dict) -> str:
    lines = [f"projections.db at {summary['db_path']}"]
    lines.append(f"  tables: {', '.join(summary.get('tables', []))}")
    for row in summary.get("game_logs_by_sport", []):
        lines.append(
            f"  {row['sport']}: {row['n']:,} rows | "
            f"{row['first_date']} -> {row['last_date']} | "
            f"{row['players']:,} distinct players"
        )
    if not summary.get("game_logs_by_sport"):
        lines.append("  player_game_logs is empty -- run --pull-nba")
    for row in summary.get("nba_by_year", []):
        lines.append(f"  NBA {row['year']}: {row['n']:,} rows")
    pi = summary.get("player_index") or {}
    if pi:
        lines.append(f"  player_index: {pi.get('total', 0):,} total, {pi.get('nba', 0):,} with NBA ID")
    if summary.get("nba_log_names_not_in_index"):
        lines.append(f"  ! {summary['nba_log_names_not_in_index']} NBA log names missing from player_index")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _iter_seasons(arg: str | None) -> Iterator[str]:
    if not arg:
        yield from DEFAULT_HISTORICAL_SEASONS
        return
    for part in arg.split(","):
        s = part.strip()
        if s:
            yield s


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="projections.db bootstrap + incremental update CLI.",
    )
    parser.add_argument("--init", action="store_true", help="Create schema (idempotent).")
    parser.add_argument("--pull-nba", action="store_true", help="Pull NBA historical via nba_api.")
    parser.add_argument(
        "--seasons",
        help="Comma-separated nba_api season strings (e.g. '2024-25,2025-26'). "
             f"Default: {','.join(DEFAULT_HISTORICAL_SEASONS)}",
    )
    parser.add_argument(
        "--season-type",
        default="Regular Season",
        choices=["Regular Season", "Playoffs", "Pre Season"],
        help="nba_api season type. Default: Regular Season.",
    )
    parser.add_argument("--verify", action="store_true", help="Print a DB summary.")
    parser.add_argument(
        "--backfill-positions",
        action="store_true",
        help=(
            "Pull NBA positions via CommonTeamRoster (~30 API calls) and "
            "write G/F/C into player_index.position for all rows that have "
            "an nba_api_id.  Use this to fix an existing DB without "
            "re-pulling game logs.  [H2'-PREREQ1]"
        ),
    )
    parser.add_argument(
        "--db-path",
        help=f"Override DB path. Default: {DB_PATH}",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="DEBUG-level logs.",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    did_anything = False

    if args.init or args.pull_nba:
        with closing(get_connection(args.db_path)) as c:
            db_file = init_db(c)
        print(f"Schema initialized at {db_file}")
        did_anything = True

    if args.pull_nba:
        totals = pull_nba_historical(
            _iter_seasons(args.seasons),
            season_type=args.season_type,
            db_path=args.db_path,
        )
        total = sum(totals.values())
        print(f"NBA pull complete: {total:,} rows across {len(totals)} season(s)")
        for s, n in totals.items():
            print(f"  {s}: {n:,}")
        did_anything = True

    if args.backfill_positions:
        updated = backfill_positions(args.db_path)
        print(f"backfill_positions: {updated} player_index rows updated with G/F/C position")
        did_anything = True

    if args.verify or not did_anything:
        summary = verify(args.db_path)
        print(_format_verify(summary))

    return 0


if __name__ == "__main__":
    sys.exit(main())
