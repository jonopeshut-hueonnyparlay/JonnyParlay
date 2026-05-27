"""engine/nhl_stats_fetcher.py — Fetch historical NHL stats from api-web.nhle.com.

Populates nhl_* tables in projections.db:
  nhl_games              — game metadata (score, date, teams, venue)
  nhl_players            — player registry (name, position)
  nhl_skater_game_stats  — per-game: SOG, goals, assists, hits, blocks, TOI, ...
  nhl_goalie_game_stats  — per-game: SA, SV, GA, TOI, starter, decision
  nhl_pull_log           — resume guard

Usage:
    python engine/nhl_stats_fetcher.py                        # 3 seasons, regular only
    python engine/nhl_stats_fetcher.py --seasons 20252026     # one season (YYYYSSSS)
    python engine/nhl_stats_fetcher.py --game-type 3          # playoffs
    python engine/nhl_stats_fetcher.py --force                # re-fetch stored games
    python engine/nhl_stats_fetcher.py --status               # print row counts

Season format is YYYYSSSS (e.g., 20232024 = 2023-24 season).
Default seasons: 20232024 20242025 20252026.

API: https://api-web.nhle.com/v1/
  Schedule: /v1/schedule/{YYYY-MM-DD}  (returns a week; follow nextStartDate)
  Boxscore: /v1/gamecenter/{game_id}/boxscore
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR

try:
    from engine_logger import get_logger
    log = get_logger("nhl_stats_fetcher")
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("nhl_stats_fetcher")

DB_PATH: Path = DATA_DIR / "projections.db"

_API_SLEEP = 0.5
_API_RETRY_MAX = 3
_API_RETRY_BACKOFF = [2, 5, 15]

_NHL_BASE = "https://api-web.nhle.com/v1"
_SCHEDULE_URL = _NHL_BASE + "/schedule/{date}"
_BOXSCORE_URL = _NHL_BASE + "/gamecenter/{game_id}/boxscore"

# gameState "OFF" = game is over (Final). Applies to regular and playoffs.
_FINAL_STATE = "OFF"

# gameType codes: 1=preseason, 2=regular, 3=playoffs
_GAME_TYPE_REGULAR = 2
_GAME_TYPE_PLAYOFF = 3

# Approximate regular-season date windows (start, day-after-last-RS-game).
# Used to bound the date iteration for regular-season pulls.
# Playoffs use the same start-of-RS date but a later cutoff.
_RS_WINDOWS: dict[int, tuple[str, str]] = {
    20232024: ("2023-10-10", "2024-04-20"),
    20242025: ("2024-10-04", "2025-04-19"),
    20252026: ("2025-10-07", "2026-04-19"),
}
_PO_WINDOWS: dict[int, tuple[str, str]] = {
    20232024: ("2024-04-20", "2024-07-01"),
    20242025: ("2025-04-19", "2025-07-01"),
    20252026: ("2026-04-19", "2026-08-01"),
}

DEFAULT_SEASONS = [20232024, 20242025, 20252026]
DEFAULT_GAME_TYPE = 2


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_NHL_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nhl_games (
    game_id       INTEGER PRIMARY KEY,
    game_date     TEXT    NOT NULL,
    season        INTEGER NOT NULL,
    game_type     INTEGER NOT NULL,   -- 2=regular, 3=playoffs
    home_team     TEXT    NOT NULL,   -- 3-letter abbreviation
    away_team     TEXT    NOT NULL,
    home_score    INTEGER,
    away_score    INTEGER,
    home_sog      INTEGER,
    away_sog      INTEGER,
    game_state    TEXT,
    venue         TEXT,
    fetched_at    TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nhlg_date   ON nhl_games(game_date);
CREATE INDEX IF NOT EXISTS idx_nhlg_season ON nhl_games(season);

CREATE TABLE IF NOT EXISTS nhl_players (
    player_id  INTEGER PRIMARY KEY,
    full_name  TEXT    NOT NULL,
    name_key   TEXT    NOT NULL,
    position   TEXT,
    updated_at TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nhlp_nk ON nhl_players(name_key);

CREATE TABLE IF NOT EXISTS nhl_skater_game_stats (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id      INTEGER NOT NULL REFERENCES nhl_games(game_id),
    player_id    INTEGER NOT NULL REFERENCES nhl_players(player_id),
    team         TEXT    NOT NULL,
    position     TEXT,
    toi_secs     INTEGER,
    goals        INTEGER,
    assists      INTEGER,
    points       INTEGER,
    plus_minus   INTEGER,
    pim          INTEGER,
    sog          INTEGER,
    hits         INTEGER,
    blocked_shots INTEGER,
    pp_goals     INTEGER,
    giveaways    INTEGER,
    takeaways    INTEGER,
    shifts       INTEGER,
    faceoff_pct  REAL,
    UNIQUE(game_id, player_id)
);
CREATE INDEX IF NOT EXISTS idx_nhlsk_player ON nhl_skater_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_nhlsk_game   ON nhl_skater_game_stats(game_id);

CREATE TABLE IF NOT EXISTS nhl_goalie_game_stats (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id      INTEGER NOT NULL REFERENCES nhl_games(game_id),
    player_id    INTEGER NOT NULL REFERENCES nhl_players(player_id),
    team         TEXT    NOT NULL,
    toi_secs     INTEGER,
    sa           INTEGER,
    sv           INTEGER,
    ga           INTEGER,
    sv_pct       REAL,
    starter      INTEGER,   -- 1 if starter
    decision     TEXT,      -- W / L / O / None
    UNIQUE(game_id, player_id)
);
CREATE INDEX IF NOT EXISTS idx_nhlg2_player ON nhl_goalie_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_nhlg2_game   ON nhl_goalie_game_stats(game_id);

CREATE TABLE IF NOT EXISTS nhl_pull_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    season        INTEGER NOT NULL,
    game_type     INTEGER NOT NULL,
    pulled_at     TEXT    DEFAULT (datetime('now')),
    games_fetched INTEGER,
    rows_skater   INTEGER,
    rows_goalie   INTEGER,
    status        TEXT    NOT NULL
);
"""


# ---------------------------------------------------------------------------
# DB connection
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
        conn.executescript(_NHL_DDL)
    log.info("NHL schema ready at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Name normalisation (same contract as MLB + NBA fetchers)
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
# TOI parsing
# ---------------------------------------------------------------------------
def _toi_to_secs(toi: str | None) -> int | None:
    """Convert 'MM:SS' TOI string to total seconds."""
    if not toi:
        return None
    try:
        parts = str(toi).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        log.debug("Cannot parse TOI: %r", toi)
        return None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def _get(url: str) -> dict[str, Any]:
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests not installed — run: pip install requests")

    last_exc: Exception | None = None
    for attempt in range(_API_RETRY_MAX):
        try:
            resp = requests.get(url, timeout=15,
                                headers={"User-Agent": "JonnyParlay-NHLFetcher/1.0"})
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < _API_RETRY_MAX - 1:
                backoff = _API_RETRY_BACKOFF[attempt]
                log.warning("API error (attempt %d/%d): %s — retry in %ds",
                            attempt + 1, _API_RETRY_MAX, exc, backoff)
                time.sleep(backoff)
    raise RuntimeError(f"NHL API failed after {_API_RETRY_MAX} attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Schedule pagination
# ---------------------------------------------------------------------------
def collect_game_ids(season: int, game_type: int) -> list[dict]:
    """Walk the weekly schedule to collect all Final games for a season+type.

    Returns list of dicts with: game_id, game_date, home_team, away_team,
    home_score, away_score, home_sog, away_sog, game_state, venue.
    """
    windows = _RS_WINDOWS if game_type == _GAME_TYPE_REGULAR else _PO_WINDOWS
    if season not in windows:
        raise ValueError(f"No date window configured for season {season}. "
                         f"Add it to _RS_WINDOWS/_PO_WINDOWS.")

    start_str, end_str = windows[season]
    end_date = date.fromisoformat(end_str)
    current_date_str = start_str
    games: list[dict] = []
    seen: set[int] = set()

    while True:
        current_date = date.fromisoformat(current_date_str)
        if current_date >= end_date:
            break

        data = _get(_SCHEDULE_URL.format(date=current_date_str))
        time.sleep(_API_SLEEP)

        for day in data.get("gameWeek", []):
            for g in day.get("games", []):
                g_season: int = g.get("season", 0)
                g_type: int = g.get("gameType", 0)
                g_state: str = g.get("gameState", "")
                g_id: int | None = g.get("id")

                if g_season != season or g_type != game_type:
                    continue
                if g_state != _FINAL_STATE:
                    continue
                if not g_id or g_id in seen:
                    continue

                seen.add(g_id)
                home = g.get("homeTeam", {})
                away = g.get("awayTeam", {})
                games.append({
                    "game_id": g_id,
                    "game_date": day.get("date", current_date_str),
                    "home_team": home.get("abbrev", ""),
                    "away_team": away.get("abbrev", ""),
                    "home_score": home.get("score"),
                    "away_score": away.get("score"),
                    "home_sog": home.get("sog"),
                    "away_sog": away.get("sog"),
                    "game_state": g_state,
                    "venue": (g.get("venue") or {}).get("default"),
                })

        next_date_str: str | None = data.get("nextStartDate")
        if not next_date_str:
            break
        current_date_str = next_date_str

    log.info("Season %d type=%d: %d final games found", season, game_type, len(games))
    return games


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------
def _upsert_player(conn: sqlite3.Connection, player_id: int,
                   full_name: str, position: str | None) -> None:
    conn.execute("""
        INSERT INTO nhl_players (player_id, full_name, name_key, position)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            full_name  = excluded.full_name,
            name_key   = excluded.name_key,
            position   = COALESCE(excluded.position, position),
            updated_at = datetime('now')
    """, (player_id, full_name, _name_key(full_name), position))


def _upsert_game(conn: sqlite3.Connection, season: int, game_type: int,
                 g: dict) -> None:
    conn.execute("""
        INSERT INTO nhl_games
            (game_id, game_date, season, game_type, home_team, away_team,
             home_score, away_score, home_sog, away_sog, game_state, venue)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id) DO UPDATE SET
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            home_sog   = excluded.home_sog,
            away_sog   = excluded.away_sog,
            fetched_at = datetime('now')
    """, (g["game_id"], g["game_date"], season, game_type,
          g["home_team"], g["away_team"],
          g["home_score"], g["away_score"],
          g["home_sog"], g["away_sog"],
          g["game_state"], g["venue"]))


# ---------------------------------------------------------------------------
# Boxscore processing
# ---------------------------------------------------------------------------
def _parse_skaters(conn: sqlite3.Connection, game_id: int, team_abbrev: str,
                   players: list[dict], skater_rows: list) -> None:
    for p in players:
        pid: int | None = p.get("playerId")
        name: str = (p.get("name") or {}).get("default", "")
        if not pid or not name:
            continue
        pos = p.get("position")
        _upsert_player(conn, pid, name, pos)
        skater_rows.append((
            game_id,
            pid,
            team_abbrev,
            pos,
            _toi_to_secs(p.get("toi")),
            p.get("goals"),
            p.get("assists"),
            p.get("points"),
            p.get("plusMinus"),
            p.get("pim"),
            p.get("sog"),
            p.get("hits"),
            p.get("blockedShots"),
            p.get("powerPlayGoals"),
            p.get("giveaways"),
            p.get("takeaways"),
            p.get("shifts"),
            p.get("faceoffWinningPctg"),
        ))


def _parse_goalies(conn: sqlite3.Connection, game_id: int, team_abbrev: str,
                   goalies: list[dict], goalie_rows: list) -> None:
    for g in goalies:
        pid: int | None = g.get("playerId")
        name: str = (g.get("name") or {}).get("default", "")
        if not pid or not name:
            continue
        _upsert_player(conn, pid, name, "G")
        starter_val = g.get("starter")
        starter = 1 if starter_val is True or starter_val == 1 else 0
        goalie_rows.append((
            game_id,
            pid,
            team_abbrev,
            _toi_to_secs(g.get("toi")),
            g.get("shotsAgainst"),
            g.get("saves"),
            g.get("goalsAgainst"),
            g.get("savePctg"),
            starter,
            g.get("decision"),
        ))


def _fetch_boxscore(conn: sqlite3.Connection, season: int, game_type: int,
                    g: dict) -> tuple[int, int]:
    """Fetch and store one game's boxscore. Returns (skater_rows, goalie_rows)."""
    game_id = g["game_id"]
    url = _BOXSCORE_URL.format(game_id=game_id)
    data = _get(url)
    time.sleep(_API_SLEEP)

    pbg = data.get("playerByGameStats", {})
    skater_rows: list = []
    goalie_rows: list = []

    for side, abbrev_key in (("homeTeam", "home_team"), ("awayTeam", "away_team")):
        team_abbrev = g[abbrev_key]
        side_data = pbg.get(side, {})
        _parse_skaters(conn, game_id, team_abbrev,
                       side_data.get("forwards", []) + side_data.get("defense", []),
                       skater_rows)
        _parse_goalies(conn, game_id, team_abbrev,
                       side_data.get("goalies", []),
                       goalie_rows)

    _upsert_game(conn, season, game_type, g)

    if skater_rows:
        conn.executemany("""
            INSERT OR IGNORE INTO nhl_skater_game_stats
                (game_id, player_id, team, position, toi_secs, goals, assists,
                 points, plus_minus, pim, sog, hits, blocked_shots, pp_goals,
                 giveaways, takeaways, shifts, faceoff_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, skater_rows)

    if goalie_rows:
        conn.executemany("""
            INSERT OR IGNORE INTO nhl_goalie_game_stats
                (game_id, player_id, team, toi_secs, sa, sv, ga, sv_pct, starter, decision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, goalie_rows)

    return len(skater_rows), len(goalie_rows)


# ---------------------------------------------------------------------------
# Season pull orchestration
# ---------------------------------------------------------------------------
def _game_already_stored(conn: sqlite3.Connection, game_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM nhl_games WHERE game_id = ?", (game_id,)
    ).fetchone() is not None


def pull_season(season: int, game_type: int = _GAME_TYPE_REGULAR,
                force: bool = False) -> None:
    ensure_schema()
    games = collect_game_ids(season, game_type)

    total_sk = total_go = fetched = errors = 0

    with get_conn() as conn:
        for g in games:
            game_id = g["game_id"]
            if not force and _game_already_stored(conn, game_id):
                continue

            try:
                ns, ng = _fetch_boxscore(conn, season, game_type, g)
                total_sk += ns
                total_go += ng
                fetched += 1

                if fetched % 50 == 0:
                    conn.commit()
                    log.info("  %d/%d games | %d skater rows | %d goalie rows",
                             fetched, len(games), total_sk, total_go)

            except Exception as exc:
                errors += 1
                log.warning("game_id=%d failed: %s", game_id, exc)
                if errors > 20:
                    log.error("Aborting season %d type=%d — too many errors",
                              season, game_type)
                    _log_pull(conn, season, game_type, fetched,
                              total_sk, total_go, "partial")
                    conn.commit()
                    return

        _log_pull(conn, season, game_type, fetched, total_sk, total_go,
                  "complete" if errors == 0 else "partial")
        conn.commit()

    log.info("Done %d type=%d: %d games | %d skater rows | %d goalie rows | %d errors",
             season, game_type, fetched, total_sk, total_go, errors)


def _log_pull(conn: sqlite3.Connection, season: int, game_type: int,
              fetched: int, rows_sk: int, rows_go: int, status: str) -> None:
    conn.execute("""
        INSERT INTO nhl_pull_log (season, game_type, games_fetched, rows_skater, rows_goalie, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (season, game_type, fetched, rows_sk, rows_go, status))


# ---------------------------------------------------------------------------
# Status report
# ---------------------------------------------------------------------------
def print_status() -> None:
    ensure_schema()
    with get_conn() as conn:
        n_games = conn.execute("SELECT COUNT(*) FROM nhl_games").fetchone()[0]
        n_players = conn.execute("SELECT COUNT(*) FROM nhl_players").fetchone()[0]
        n_sk = conn.execute("SELECT COUNT(*) FROM nhl_skater_game_stats").fetchone()[0]
        n_go = conn.execute("SELECT COUNT(*) FROM nhl_goalie_game_stats").fetchone()[0]

        print(f"\n=== NHL DB ({DB_PATH}) ===")
        print(f"  nhl_games:               {n_games:>7,}")
        print(f"  nhl_players:             {n_players:>7,}")
        print(f"  nhl_skater_game_stats:   {n_sk:>7,}")
        print(f"  nhl_goalie_game_stats:   {n_go:>7,}")

        rows = conn.execute("""
            SELECT season, game_type, COUNT(*) AS n,
                   MIN(game_date) AS first, MAX(game_date) AS last
            FROM nhl_games GROUP BY season, game_type ORDER BY season, game_type
        """).fetchall()
        if rows:
            print("\n  Games by season:")
            for r in rows:
                gtype = "RS" if r["game_type"] == 2 else "PO"
                print(f"    {r['season']} {gtype}:  {r['n']:>4} games"
                      f"  ({r['first']} -> {r['last']})")

        logs = conn.execute("""
            SELECT season, game_type, status, games_fetched, pulled_at
            FROM nhl_pull_log ORDER BY pulled_at DESC LIMIT 10
        """).fetchall()
        if logs:
            print("\n  Recent pull_log:")
            for r in logs:
                gtype = "RS" if r["game_type"] == 2 else "PO"
                print(f"    {r['season']} {gtype}  {r['status']:<8} "
                      f"{r['games_fetched']} games  {r['pulled_at']}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch NHL historical stats into projections.db nhl_* tables"
    )
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=DEFAULT_SEASONS,
        help="Season identifiers in YYYYSSSS format "
             "(default: 20232024 20242025 20252026)",
    )
    parser.add_argument(
        "--game-type", type=int, default=DEFAULT_GAME_TYPE, choices=[2, 3],
        help="2=Regular Season (default), 3=Playoffs",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch games already in the DB",
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
    for season in args.seasons:
        pull_season(season, game_type=args.game_type, force=args.force)

    print_status()


if __name__ == "__main__":
    main()
