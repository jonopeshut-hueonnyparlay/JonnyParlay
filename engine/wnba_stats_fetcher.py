"""engine/wnba_stats_fetcher.py — Fetch historical WNBA stats from the NBA Stats API.

Populates wnba_* tables in projections.db:
  wnba_players          — player registry
  wnba_player_game_stats — per-game box scores (PTS, REB, AST, 3PM, ...)
  wnba_pull_log         — resume guard

Uses the NBA Stats API with LeagueID='10' (WNBA). The leaguegamelog endpoint
returns all player-game stats for an entire season in a single call.

Usage:
    python engine/wnba_stats_fetcher.py                         # 2023-2026, RS
    python engine/wnba_stats_fetcher.py --seasons 2025 2026     # specific years
    python engine/wnba_stats_fetcher.py --season-type Playoffs  # playoff data
    python engine/wnba_stats_fetcher.py --force                 # re-pull seasons
    python engine/wnba_stats_fetcher.py --status                # print row counts

Unblocks WNBA sigma calibration for PTS, REB, AST, 3PM once sufficient game logs
are stored. Also enables WNBA COMBO rho refit at n=500+ player-games.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR

try:
    from engine_logger import get_logger
    log = get_logger("wnba_stats_fetcher")
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("wnba_stats_fetcher")

DB_PATH: Path = DATA_DIR / "projections.db"

_API_SLEEP = 2.0  # NBA Stats API rate-limits aggressively; 2s is safe
_API_RETRY_MAX = 3
_API_RETRY_BACKOFF = [5, 15, 30]

_STATS_BASE = "https://stats.wnba.com/stats"
_GAMELOG_URL = _STATS_BASE + "/leaguegamelog"

_NBA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.wnba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.wnba.com",
}

DEFAULT_SEASONS = [2023, 2024, 2025, 2026]
DEFAULT_SEASON_TYPE = "Regular Season"

_SEASON_TYPES = ["Regular Season", "Playoffs"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_WNBA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS wnba_players (
    player_id  INTEGER PRIMARY KEY,
    full_name  TEXT    NOT NULL,
    name_key   TEXT    NOT NULL,
    updated_at TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_wnbap_nk ON wnba_players(name_key);

CREATE TABLE IF NOT EXISTS wnba_player_game_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    season      INTEGER NOT NULL,
    season_type TEXT    NOT NULL,
    player_id   INTEGER NOT NULL REFERENCES wnba_players(player_id),
    player_name TEXT    NOT NULL,
    team_id     INTEGER,
    team_abbrev TEXT,
    game_id     TEXT    NOT NULL,
    game_date   TEXT    NOT NULL,
    matchup     TEXT,
    wl          TEXT,
    min         REAL,
    fgm         INTEGER,
    fga         INTEGER,
    fg3m        INTEGER,
    fg3a        INTEGER,
    ftm         INTEGER,
    fta         INTEGER,
    oreb        INTEGER,
    dreb        INTEGER,
    reb         INTEGER,
    ast         INTEGER,
    stl         INTEGER,
    blk         INTEGER,
    tov         INTEGER,
    pf          INTEGER,
    pts         INTEGER,
    plus_minus  REAL,
    UNIQUE(game_id, player_id)
);
CREATE INDEX IF NOT EXISTS idx_wnbapgs_player ON wnba_player_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_wnbapgs_game   ON wnba_player_game_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_wnbapgs_season ON wnba_player_game_stats(season, season_type);

CREATE TABLE IF NOT EXISTS wnba_pull_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    season        INTEGER NOT NULL,
    season_type   TEXT    NOT NULL,
    pulled_at     TEXT    DEFAULT (datetime('now')),
    rows_upserted INTEGER,
    status        TEXT    NOT NULL
);
"""

# Column order from the NBA Stats API leaguegamelog endpoint
_GAMELOG_COLS = [
    "season_id", "player_id", "player_name", "team_id", "team_abbreviation",
    "team_name", "game_id", "game_date", "matchup", "wl",
    "min", "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct",
    "ftm", "fta", "ft_pct", "oreb", "dreb", "reb",
    "ast", "stl", "blk", "tov", "pf", "pts", "plus_minus",
    "fantasy_pts", "video_available",
]


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 20000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def ensure_schema() -> None:
    with get_conn() as conn:
        conn.executescript(_WNBA_DDL)
    log.info("WNBA schema ready at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------
try:
    from name_utils import fold_name as _fold_name
except ImportError:
    import re as _re
    import unicodedata as _ud

    def _fold_name(name: str) -> str:  # type: ignore[misc]
        if not name:
            return ""
        n = _ud.normalize("NFD", str(name))
        n = "".join(c for c in n if _ud.category(c) != "Mn")
        n = n.lower()
        n = _re.sub(r"\b(jr\.?|sr\.?|ii|iii|iv|v)\b", "", n)
        n = _re.sub(r"[^a-z ]", "", n)
        return n.strip()


def _name_key(name: str) -> str:
    parts = _fold_name(name).split()
    if len(parts) < 2:
        return _fold_name(name)
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    while len(parts) >= 2 and parts[-1] in suffixes:
        parts.pop()
    return f"{parts[-1]}_{parts[0][:3]}"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def _fetch_gamelog(season_year: int, season_type: str) -> list[list]:
    """Fetch all player-game rows for a WNBA season from the WNBA Stats API."""
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests not installed — run: pip install requests")

    params = {
        "Counter": 0,
        "DateFrom": "",
        "DateTo": "",
        "Direction": "ASC",
        "LeagueID": "10",
        "PlayerOrTeam": "P",
        "Season": str(season_year),
        "SeasonType": season_type,
        "Sorter": "DATE",
    }

    last_exc: Exception | None = None
    for attempt in range(_API_RETRY_MAX):
        try:
            resp = requests.get(_GAMELOG_URL, params=params, headers=_NBA_HEADERS,
                                timeout=30)
            resp.raise_for_status()
            data = resp.json()
            result_sets = data.get("resultSets", [])
            if not result_sets:
                return []
            return result_sets[0].get("rowSet", [])
        except Exception as exc:
            last_exc = exc
            if attempt < _API_RETRY_MAX - 1:
                backoff = _API_RETRY_BACKOFF[attempt]
                log.warning("API error (attempt %d/%d): %s — retry in %ds",
                            attempt + 1, _API_RETRY_MAX, exc, backoff)
                time.sleep(backoff)

    raise RuntimeError(
        f"NBA Stats API failed after {_API_RETRY_MAX} attempts: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Season pull
# ---------------------------------------------------------------------------
def _already_pulled(conn: sqlite3.Connection, season: int,
                    season_type: str) -> bool:
    row = conn.execute("""
        SELECT status FROM wnba_pull_log
        WHERE season = ? AND season_type = ?
        ORDER BY pulled_at DESC LIMIT 1
    """, (season, season_type)).fetchone()
    return row is not None and row["status"] == "complete"


def pull_season(season: int, season_type: str = DEFAULT_SEASON_TYPE,
                force: bool = False) -> None:
    ensure_schema()

    with get_conn() as conn:
        if not force and _already_pulled(conn, season, season_type):
            log.info("Season %d %s already complete — skipping (use --force to re-pull)",
                     season, season_type)
            return

    log.info("Fetching WNBA %d %s...", season, season_type)
    rows = _fetch_gamelog(season, season_type)
    time.sleep(_API_SLEEP)

    if not rows:
        log.info("No data returned for %d %s", season, season_type)
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO wnba_pull_log (season, season_type, rows_upserted, status)
                VALUES (?, ?, 0, 'complete')
            """, (season, season_type))
            conn.commit()
        return

    log.info("  %d player-game rows returned", len(rows))

    player_rows: list = []
    stat_rows: list = []

    for row in rows:
        if len(row) < 30:
            continue
        # Unpack by column position (matches _GAMELOG_COLS order)
        (season_id, player_id, player_name, team_id, team_abbrev,
         _team_name, game_id, game_date, matchup, wl,
         min_val, fgm, fga, _fg_pct, fg3m, fg3a, _fg3_pct,
         ftm, fta, _ft_pct, oreb, dreb, reb,
         ast, stl, blk, tov, pf, pts, plus_minus, *_rest) = row

        if not player_id or not game_id:
            continue

        player_rows.append((
            player_id,
            player_name or "",
            _name_key(player_name or ""),
        ))
        stat_rows.append((
            season,
            season_type,
            player_id,
            player_name or "",
            team_id,
            team_abbrev,
            str(game_id),
            game_date,
            matchup,
            wl,
            min_val,
            fgm, fga, fg3m, fg3a, ftm, fta,
            oreb, dreb, reb, ast, stl, blk, tov, pf, pts,
            plus_minus,
        ))

    with get_conn() as conn:
        if player_rows:
            conn.executemany("""
                INSERT INTO wnba_players (player_id, full_name, name_key)
                VALUES (?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    full_name  = excluded.full_name,
                    name_key   = excluded.name_key,
                    updated_at = datetime('now')
            """, player_rows)

        inserted = 0
        if stat_rows:
            cur = conn.executemany("""
                INSERT OR IGNORE INTO wnba_player_game_stats
                    (season, season_type, player_id, player_name, team_id, team_abbrev,
                     game_id, game_date, matchup, wl,
                     min, fgm, fga, fg3m, fg3a, ftm, fta,
                     oreb, dreb, reb, ast, stl, blk, tov, pf, pts, plus_minus)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, stat_rows)
            inserted = cur.rowcount if cur.rowcount >= 0 else len(stat_rows)

        conn.execute("""
            INSERT INTO wnba_pull_log (season, season_type, rows_upserted, status)
            VALUES (?, ?, ?, 'complete')
        """, (season, season_type, inserted))
        conn.commit()

    log.info("Done %d %s: %d rows upserted", season, season_type, inserted)


# ---------------------------------------------------------------------------
# Status report
# ---------------------------------------------------------------------------
def print_status() -> None:
    ensure_schema()
    with get_conn() as conn:
        n_players = conn.execute("SELECT COUNT(*) FROM wnba_players").fetchone()[0]
        n_stats = conn.execute("SELECT COUNT(*) FROM wnba_player_game_stats").fetchone()[0]

        print(f"\n=== WNBA DB ({DB_PATH}) ===")
        print(f"  wnba_players:            {n_players:>7,}")
        print(f"  wnba_player_game_stats:  {n_stats:>7,}")

        rows = conn.execute("""
            SELECT season, season_type, COUNT(*) AS n,
                   MIN(game_date) AS first, MAX(game_date) AS last
            FROM wnba_player_game_stats
            GROUP BY season, season_type ORDER BY season, season_type
        """).fetchall()
        if rows:
            print("\n  Stats by season:")
            for r in rows:
                print(f"    {r['season']} {r['season_type'][:2]}:  "
                      f"{r['n']:>5} player-games"
                      f"  ({r['first']} -> {r['last']})")

        logs = conn.execute("""
            SELECT season, season_type, status, rows_upserted, pulled_at
            FROM wnba_pull_log ORDER BY pulled_at DESC LIMIT 10
        """).fetchall()
        if logs:
            print("\n  Recent pull_log:")
            for r in logs:
                print(f"    {r['season']} {r['season_type'][:2]}  {r['status']:<8} "
                      f"{r['rows_upserted']} rows  {r['pulled_at']}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch WNBA historical stats into projections.db wnba_* tables"
    )
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=DEFAULT_SEASONS,
        help="Season years (default: 2023 2024 2025 2026)",
    )
    parser.add_argument(
        "--season-type", default=DEFAULT_SEASON_TYPE,
        choices=_SEASON_TYPES,
        help="Season type (default: 'Regular Season')",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-pull seasons already marked complete",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print row counts and exit",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.status:
        print_status()
        return

    ensure_schema()
    for year in args.seasons:
        pull_season(year, season_type=args.season_type, force=args.force)

    print_status()


if __name__ == "__main__":
    main()
