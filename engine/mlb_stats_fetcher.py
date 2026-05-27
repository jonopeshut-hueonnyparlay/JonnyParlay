"""engine/mlb_stats_fetcher.py — Fetch historical MLB stats from the MLB Stats API.

Populates mlb_* tables in projections.db:
  mlb_games              — game metadata (score, date, teams, venue)
  mlb_players            — player registry (name, position, bats/throws)
  mlb_pitcher_game_stats — per-game pitching (K, IP, H, R, ER, BB, HR, HBP, BF, PC)
  mlb_batter_game_stats  — per-game batting (H, HR, RBI, R, BB, SO, SB, TB, 2B, 3B, ...)
  mlb_pull_log           — resume guard (season + game_type + status)

Usage:
    python engine/mlb_stats_fetcher.py                          # 2023-2026, R only
    python engine/mlb_stats_fetcher.py --seasons 2025 2026      # specific years
    python engine/mlb_stats_fetcher.py --game-type D            # Division Series
    python engine/mlb_stats_fetcher.py --force                  # re-pull completed
    python engine/mlb_stats_fetcher.py --status                 # print row counts

MLB Stats API game_type codes: R=Regular, F=Wild Card, D=Division Series,
L=League Championship, W=World Series, S=Spring Training.

Games with status != Final/Completed are skipped (handles in-progress 2026).
Resume-safe: already-stored game_pks are skipped automatically.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR

try:
    from engine_logger import get_logger
    log = get_logger("mlb_stats_fetcher")
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("mlb_stats_fetcher")

DB_PATH: Path = DATA_DIR / "projections.db"

_API_SLEEP = 0.5
_API_RETRY_MAX = 3
_API_RETRY_BACKOFF = [2, 5, 15]

_MLB_BASE = "https://statsapi.mlb.com/api/v1"
_SCHEDULE_URL = (
    _MLB_BASE
    + "/schedule?sportId=1&season={year}&gameType={game_type}"
    + "&hydrate=teams,venue,linescore"
)
_BOXSCORE_URL = _MLB_BASE + "/game/{game_pk}/boxscore"

_HAS_STATS_STATES = {"Final", "Game Over", "Completed Early"}

DEFAULT_SEASONS = [2023, 2024, 2025, 2026]
DEFAULT_GAME_TYPE = "R"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_MLB_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mlb_games (
    game_pk       INTEGER PRIMARY KEY,
    game_date     TEXT    NOT NULL,
    season        INTEGER NOT NULL,
    game_type     TEXT    NOT NULL,
    home_team_id  INTEGER NOT NULL,
    away_team_id  INTEGER NOT NULL,
    home_score    INTEGER,
    away_score    INTEGER,
    status        TEXT    NOT NULL,
    venue         TEXT,
    fetched_at    TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mlbg_date   ON mlb_games(game_date);
CREATE INDEX IF NOT EXISTS idx_mlbg_season ON mlb_games(season);

CREATE TABLE IF NOT EXISTS mlb_players (
    player_id        INTEGER PRIMARY KEY,
    full_name        TEXT    NOT NULL,
    name_key         TEXT    NOT NULL,
    primary_position TEXT,
    bats             TEXT,
    throws           TEXT,
    updated_at       TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mlbp_nk ON mlb_players(name_key);

CREATE TABLE IF NOT EXISTS mlb_pitcher_game_stats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk    INTEGER NOT NULL REFERENCES mlb_games(game_pk),
    player_id  INTEGER NOT NULL REFERENCES mlb_players(player_id),
    team_id    INTEGER NOT NULL,
    is_starter INTEGER NOT NULL DEFAULT 0,
    ip_outs    INTEGER,
    ip_dec     TEXT,
    h          INTEGER,
    r          INTEGER,
    er         INTEGER,
    bb         INTEGER,
    k          INTEGER,
    hr         INTEGER,
    hbp        INTEGER,
    bf         INTEGER,
    pc         INTEGER,
    strikes    INTEGER,
    UNIQUE(game_pk, player_id)
);
CREATE INDEX IF NOT EXISTS idx_mlbpit_player ON mlb_pitcher_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_mlbpit_game   ON mlb_pitcher_game_stats(game_pk);

CREATE TABLE IF NOT EXISTS mlb_batter_game_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk       INTEGER NOT NULL REFERENCES mlb_games(game_pk),
    player_id     INTEGER NOT NULL REFERENCES mlb_players(player_id),
    team_id       INTEGER NOT NULL,
    batting_order INTEGER,
    ab            INTEGER,
    r             INTEGER,
    h             INTEGER,
    doubles       INTEGER,
    triples       INTEGER,
    hr            INTEGER,
    rbi           INTEGER,
    bb            INTEGER,
    k             INTEGER,
    sb            INTEGER,
    cs            INTEGER,
    hbp           INTEGER,
    sf            INTEGER,
    tb            INTEGER,
    lob           INTEGER,
    UNIQUE(game_pk, player_id)
);
CREATE INDEX IF NOT EXISTS idx_mlbbat_player ON mlb_batter_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_mlbbat_game   ON mlb_batter_game_stats(game_pk);

CREATE TABLE IF NOT EXISTS mlb_pull_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    season        INTEGER NOT NULL,
    game_type     TEXT    NOT NULL,
    pulled_at     TEXT    DEFAULT (datetime('now')),
    games_fetched INTEGER,
    rows_pitching INTEGER,
    rows_batting  INTEGER,
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
        conn.executescript(_MLB_DDL)
    log.info("MLB schema ready at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Name normalisation (mirrors mlb_starter_fetcher / name_utils contract)
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
# IP string → outs
# ---------------------------------------------------------------------------
def _ip_to_outs(ip_str: str | None) -> int | None:
    """Convert MLB IP string to total outs recorded. '6.1' = 6 inn + 1 out = 19."""
    if not ip_str:
        return None
    try:
        s = str(ip_str).strip()
        if "." in s:
            whole, frac = s.split(".", 1)
            return int(whole) * 3 + int(frac)
        return int(s) * 3
    except (ValueError, TypeError):
        log.debug("Cannot parse IP: %r", ip_str)
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
                                headers={"User-Agent": "JonnyParlay-MLBFetcher/1.0"})
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < _API_RETRY_MAX - 1:
                backoff = _API_RETRY_BACKOFF[attempt]
                log.warning("API error (attempt %d/%d): %s — retry in %ds",
                            attempt + 1, _API_RETRY_MAX, exc, backoff)
                time.sleep(backoff)
    raise RuntimeError(f"MLB API failed after {_API_RETRY_MAX} attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------
def fetch_schedule(year: int, game_type: str = "R") -> list[dict]:
    """Return list of raw game dicts for one season year + game_type."""
    url = _SCHEDULE_URL.format(year=year, game_type=game_type)
    log.info("Fetching schedule year=%d game_type=%s", year, game_type)
    data = _get(url)
    games: list[dict] = []
    for date_block in data.get("dates", []):
        for g in date_block.get("games", []):
            games.append(g)
    log.info("  %d total games in schedule", len(games))
    return games


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------
def _upsert_player(conn: sqlite3.Connection, player_id: int, full_name: str,
                   primary_position: str | None = None,
                   bats: str | None = None,
                   throws: str | None = None) -> None:
    conn.execute("""
        INSERT INTO mlb_players
            (player_id, full_name, name_key, primary_position, bats, throws)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            full_name        = excluded.full_name,
            name_key         = excluded.name_key,
            primary_position = COALESCE(excluded.primary_position, primary_position),
            bats             = COALESCE(excluded.bats, bats),
            throws           = COALESCE(excluded.throws, throws),
            updated_at       = datetime('now')
    """, (player_id, full_name, _name_key(full_name), primary_position, bats, throws))


def _upsert_game(conn: sqlite3.Connection, game_pk: int, game_date: str,
                 season: int, game_type: str, home_id: int, away_id: int,
                 home_score: int | None, away_score: int | None,
                 status: str, venue: str | None) -> None:
    conn.execute("""
        INSERT INTO mlb_games
            (game_pk, game_date, season, game_type, home_team_id, away_team_id,
             home_score, away_score, status, venue)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_pk) DO UPDATE SET
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            status     = excluded.status,
            fetched_at = datetime('now')
    """, (game_pk, game_date, season, game_type, home_id, away_id,
          home_score, away_score, status, venue))


# ---------------------------------------------------------------------------
# Boxscore parsing
# ---------------------------------------------------------------------------
def _parse_side(conn: sqlite3.Connection, side_data: dict, game_pk: int,
                pitcher_rows: list, batter_rows: list) -> None:
    """Extract pitcher + batter rows from one side (home/away) of a boxscore."""
    team_id: int | None = side_data.get("team", {}).get("id")
    if not team_id:
        return

    # First entry in pitchers list is the starter
    pitchers_list: list[int] = side_data.get("pitchers", [])
    starter_id: int | None = pitchers_list[0] if pitchers_list else None

    for _key, pdata in side_data.get("players", {}).items():
        person = pdata.get("person", {})
        pid: int | None = person.get("id")
        full_name: str = person.get("fullName", "")
        if not pid or not full_name:
            continue

        pos_info = pdata.get("position", {})
        pos_abbrev = pos_info.get("abbreviation") or pos_info.get("type") or None
        bat_side = (pdata.get("batSide") or {}).get("code")
        pitch_hand = (pdata.get("pitchHand") or {}).get("code")

        _upsert_player(conn, pid, full_name,
                       primary_position=pos_abbrev,
                       bats=bat_side,
                       throws=pitch_hand)

        stats = pdata.get("stats", {})

        # -- Pitching --
        pit = stats.get("pitching", {})
        ip_str = pit.get("inningsPitched", "")
        if ip_str:  # any IP value means this player pitched
            pitcher_rows.append((
                game_pk,
                pid,
                team_id,
                1 if pid == starter_id else 0,
                _ip_to_outs(ip_str),
                str(ip_str),
                pit.get("hits"),
                pit.get("runs"),
                pit.get("earnedRuns"),
                pit.get("baseOnBalls"),
                pit.get("strikeOuts"),
                pit.get("homeRuns"),
                pit.get("hitBatsmen"),
                pit.get("battersFaced"),
                pit.get("numberOfPitches") or pit.get("pitchesThrown"),
                pit.get("strikes"),
            ))

        # -- Batting --
        bat = stats.get("batting", {})
        if bat.get("atBats") is not None:  # player appeared in the batting lineup
            order_str = pdata.get("battingOrder", "")
            batting_order = int(order_str) if order_str else None
            batter_rows.append((
                game_pk,
                pid,
                team_id,
                batting_order,
                bat.get("atBats"),
                bat.get("runs"),
                bat.get("hits"),
                bat.get("doubles"),
                bat.get("triples"),
                bat.get("homeRuns"),
                bat.get("rbi"),
                bat.get("baseOnBalls"),
                bat.get("strikeOuts"),
                bat.get("stolenBases"),
                bat.get("caughtStealing"),
                bat.get("hitByPitch"),
                bat.get("sacFlies"),
                bat.get("totalBases"),
                bat.get("leftOnBase"),
            ))


def _fetch_boxscore(conn: sqlite3.Connection, game_pk: int,
                    game_date: str, season: int, game_type: str,
                    home_id: int, away_id: int,
                    home_score: int | None, away_score: int | None,
                    status: str, venue: str | None) -> tuple[int, int]:
    """Fetch + store one game. Returns (pitcher_rows_inserted, batter_rows_inserted)."""
    url = _BOXSCORE_URL.format(game_pk=game_pk)
    data = _get(url)
    time.sleep(_API_SLEEP)

    teams = data.get("teams", {})
    pitcher_rows: list = []
    batter_rows: list = []

    for side in ("home", "away"):
        _parse_side(conn, teams.get(side, {}), game_pk, pitcher_rows, batter_rows)

    _upsert_game(conn, game_pk, game_date, season, game_type,
                 home_id, away_id, home_score, away_score, status, venue)

    if pitcher_rows:
        conn.executemany("""
            INSERT OR IGNORE INTO mlb_pitcher_game_stats
                (game_pk, player_id, team_id, is_starter, ip_outs, ip_dec,
                 h, r, er, bb, k, hr, hbp, bf, pc, strikes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, pitcher_rows)

    if batter_rows:
        conn.executemany("""
            INSERT OR IGNORE INTO mlb_batter_game_stats
                (game_pk, player_id, team_id, batting_order,
                 ab, r, h, doubles, triples, hr, rbi, bb, k,
                 sb, cs, hbp, sf, tb, lob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batter_rows)

    return len(pitcher_rows), len(batter_rows)


# ---------------------------------------------------------------------------
# Season orchestration
# ---------------------------------------------------------------------------
def _game_already_stored(conn: sqlite3.Connection, game_pk: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM mlb_games WHERE game_pk = ?", (game_pk,)
    ).fetchone() is not None


def pull_season(year: int, game_type: str = "R", force: bool = False) -> None:
    ensure_schema()
    schedule = fetch_schedule(year, game_type)

    eligible = [
        g for g in schedule
        if g.get("status", {}).get("detailedState", "") in _HAS_STATS_STATES
    ]
    log.info("Season %d %s: %d final games to fetch", year, game_type, len(eligible))

    total_pit = total_bat = fetched = errors = 0

    with get_conn() as conn:
        for g in eligible:
            game_pk: int | None = g.get("gamePk")
            if not game_pk:
                continue
            if not force and _game_already_stored(conn, game_pk):
                continue

            teams_raw = g.get("teams", {})
            home_id: int | None = teams_raw.get("home", {}).get("team", {}).get("id")
            away_id: int | None = teams_raw.get("away", {}).get("team", {}).get("id")
            if not home_id or not away_id:
                log.debug("Skipping game_pk=%d — missing team IDs", game_pk)
                continue

            game_date: str = g.get("gameDate", "")[:10]
            status: str = g.get("status", {}).get("detailedState", "")
            home_score = teams_raw.get("home", {}).get("score")
            away_score = teams_raw.get("away", {}).get("score")
            venue = (g.get("venue") or {}).get("name")

            try:
                np, nb = _fetch_boxscore(
                    conn, game_pk, game_date, year, game_type,
                    home_id, away_id, home_score, away_score, status, venue,
                )
                total_pit += np
                total_bat += nb
                fetched += 1

                if fetched % 50 == 0:
                    conn.commit()
                    log.info("  %d/%d games | %d pit rows | %d bat rows",
                             fetched, len(eligible), total_pit, total_bat)

            except Exception as exc:
                errors += 1
                log.warning("game_pk=%d failed: %s", game_pk, exc)
                if errors > 20:
                    log.error("Aborting season %d %s — too many errors", year, game_type)
                    _log_pull(conn, year, game_type, fetched, total_pit, total_bat, "partial")
                    conn.commit()
                    return

        _log_pull(conn, year, game_type, fetched, total_pit, total_bat,
                  "complete" if errors == 0 else "partial")
        conn.commit()

    log.info("Done %d %s: %d games | %d pit rows | %d bat rows | %d errors",
             year, game_type, fetched, total_pit, total_bat, errors)


def _log_pull(conn: sqlite3.Connection, year: int, game_type: str,
              fetched: int, rows_pit: int, rows_bat: int, status: str) -> None:
    conn.execute("""
        INSERT INTO mlb_pull_log (season, game_type, games_fetched, rows_pitching, rows_batting, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (year, game_type, fetched, rows_pit, rows_bat, status))


# ---------------------------------------------------------------------------
# Status report
# ---------------------------------------------------------------------------
def print_status() -> None:
    ensure_schema()
    with get_conn() as conn:
        n_games = conn.execute("SELECT COUNT(*) FROM mlb_games").fetchone()[0]
        n_players = conn.execute("SELECT COUNT(*) FROM mlb_players").fetchone()[0]
        n_pit = conn.execute("SELECT COUNT(*) FROM mlb_pitcher_game_stats").fetchone()[0]
        n_bat = conn.execute("SELECT COUNT(*) FROM mlb_batter_game_stats").fetchone()[0]

        print(f"\n=== MLB DB ({DB_PATH}) ===")
        print(f"  mlb_games:              {n_games:>7,}")
        print(f"  mlb_players:            {n_players:>7,}")
        print(f"  mlb_pitcher_game_stats: {n_pit:>7,}")
        print(f"  mlb_batter_game_stats:  {n_bat:>7,}")

        rows = conn.execute("""
            SELECT season, game_type, COUNT(*) AS n,
                   MIN(game_date) AS first, MAX(game_date) AS last
            FROM mlb_games GROUP BY season, game_type ORDER BY season, game_type
        """).fetchall()
        if rows:
            print("\n  Games by season:")
            for r in rows:
                print(f"    {r['season']} {r['game_type']}:  {r['n']:>4} games"
                      f"  ({r['first']} -> {r['last']})")

        logs = conn.execute("""
            SELECT season, game_type, status, games_fetched, pulled_at
            FROM mlb_pull_log ORDER BY pulled_at DESC LIMIT 10
        """).fetchall()
        if logs:
            print("\n  Recent pull_log:")
            for r in logs:
                print(f"    {r['season']} {r['game_type']}  {r['status']:<8} "
                      f"{r['games_fetched']} games  {r['pulled_at']}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch MLB historical stats into projections.db mlb_* tables"
    )
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=DEFAULT_SEASONS,
        help="Calendar years to fetch (default: 2023 2024 2025 2026)",
    )
    parser.add_argument(
        "--game-type", default=DEFAULT_GAME_TYPE,
        help="MLB Stats API game_type: R=Regular, F=Wild Card, D=Division, "
             "L=LCS, W=World Series (default: R)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch games already in the DB (overwrites game metadata, "
             "skips duplicate stat rows via INSERT OR IGNORE)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print row counts and exit — no fetching",
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
        pull_season(year, game_type=args.game_type, force=args.force)

    print_status()


if __name__ == "__main__":
    main()
