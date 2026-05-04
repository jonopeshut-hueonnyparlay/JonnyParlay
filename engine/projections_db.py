"""engine/projections_db.py — SQLite schema + nba_api historical pull.

Architecture A+ (role-conditional rates x decomposed minutes regression).
Reference: memory/projects/custom-projection-engine-research-report.md

CLI:
  python engine/projections_db.py                  # DB status
  python engine/projections_db.py --pull            # pull all seasons
  python engine/projections_db.py --pull --seasons 2024-25,2025-26
  python engine/projections_db.py --pull --reset    # wipe + repull
  python engine/projections_db.py --verify
  python engine/projections_db.py --compute-splits
"""
from __future__ import annotations
import argparse, logging, sqlite3, sys, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from paths import DATA_DIR

try:
    from engine_logger import get_logger
    log = get_logger("projections_db")
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("projections_db")

DB_PATH: Path = DATA_DIR / "projections.db"

# Era weights — exponential decay, half-life ≈ 2.8 seasons (Research Brief 5, 2026-05-02).
# Formula: exp(-0.25 * seasons_ago). Bubble/compressed seasons additionally down-weighted.
# 2019-20 and 2020-21 are included in the lookup but NOT in DEFAULT_SEASONS — they must be
# pulled explicitly via pull_all_data(seasons=[...]) before they contribute to projections.
SEASON_ERA_WEIGHTS: Dict[str, float] = {
    "2019-20": 0.11,  # bubble — exp(-0.25*6) * 0.5 ; not in DEFAULT_SEASONS
    "2020-21": 0.20,  # compressed — exp(-0.25*5) * 0.7 ; not in DEFAULT_SEASONS
    "2021-22": 0.37,  # exp(-0.25*4) ; was 0.15
    "2022-23": 0.47,  # exp(-0.25*3) ; was 0.30
    "2023-24": 0.61,  # exp(-0.25*2) ; was 0.50
    "2024-25": 0.78,  # exp(-0.25*1) ; was 0.75
    "2025-26": 1.00,
}
DEFAULT_SEASONS: List[str] = [
    "2021-22", "2022-23", "2023-24", "2024-25", "2025-26",
]

_API_SLEEP        = 0.65
_API_RETRY_MAX    = 3
_API_RETRY_BACKOFF = [2, 5, 15]
_CLIP_LO, _CLIP_HI = 0.80, 1.20
_DEF_STATS  = ["pts", "reb", "ast", "fg3m", "fg3a", "stl", "blk", "tov"]
MIN_SPLIT_GAMES = 5  # M8: minimum games for a team's defensive split to be stored
_POS_GROUPS = ["G", "F", "C"]


def _position_group(pos: str) -> str:
    p = str(pos).strip().upper()
    if not p or p == "NONE": return "F"
    if p.startswith("G"):    return "G"
    if p.startswith("C"):    return "C"
    return "F"


# ---------------------------------------------------------------------------
# SCHEMA
# ---------------------------------------------------------------------------
_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
    player_id  INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    name_key   TEXT NOT NULL,
    position   TEXT,
    team_id    INTEGER,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_players_nk ON players(name_key);

CREATE TABLE IF NOT EXISTS teams (
    team_id      INTEGER PRIMARY KEY,
    abbreviation TEXT NOT NULL,
    name         TEXT NOT NULL,
    city         TEXT
);

CREATE TABLE IF NOT EXISTS games (
    game_id      TEXT PRIMARY KEY,
    game_date    TEXT NOT NULL,
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    season       TEXT NOT NULL,
    season_type  TEXT NOT NULL,
    era_weight   REAL NOT NULL DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS idx_games_date   ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);

CREATE TABLE IF NOT EXISTS player_game_stats (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id      TEXT    NOT NULL REFERENCES games(game_id),
    player_id    INTEGER NOT NULL REFERENCES players(player_id),
    team_id      INTEGER NOT NULL REFERENCES teams(team_id),
    min          REAL,
    fgm INTEGER, fga INTEGER,
    fg3m INTEGER, fg3a INTEGER,
    ftm INTEGER,  fta INTEGER,
    oreb INTEGER, dreb INTEGER, reb INTEGER,
    ast INTEGER,  stl INTEGER,  blk INTEGER,
    tov INTEGER,  pf  INTEGER,  pts INTEGER,
    plus_minus   REAL,
    starter_flag INTEGER DEFAULT 0,
    ts_pct       REAL,
    UNIQUE(game_id, player_id)
);
CREATE INDEX IF NOT EXISTS idx_pgs_player ON player_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_pgs_game   ON player_game_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_pgs_pid_gid ON player_game_stats(player_id, game_id);

-- Team pace + ratings per season
CREATE TABLE IF NOT EXISTS team_season_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     INTEGER NOT NULL REFERENCES teams(team_id),
    season      TEXT NOT NULL,
    season_type TEXT NOT NULL DEFAULT 'Regular Season',
    pace        REAL,
    off_rtg     REAL,
    def_rtg     REAL,
    net_rtg     REAL,
    UNIQUE(team_id, season, season_type)
);
CREATE INDEX IF NOT EXISTS idx_tss ON team_season_stats(team_id, season);

-- Matchup factor: opp-allowed rates by (position_group, stat)
-- ratio > 1.0 = soft (favour OVER); < 1.0 = tough; clipped [0.80, 1.20]
CREATE TABLE IF NOT EXISTS team_def_splits (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id        INTEGER NOT NULL REFERENCES teams(team_id),
    season         TEXT NOT NULL,
    position_group TEXT NOT NULL,
    stat           TEXT NOT NULL,
    avg_allowed    REAL,
    league_avg     REAL,
    ratio          REAL,
    games_sample   INTEGER,
    UNIQUE(team_id, season, position_group, stat)
);
CREATE INDEX IF NOT EXISTS idx_tds ON team_def_splits(team_id, season);

-- Resume guard
CREATE TABLE IF NOT EXISTS pull_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    season        TEXT NOT NULL,
    endpoint      TEXT NOT NULL,
    pulled_at     TEXT DEFAULT (datetime('now')),
    rows_upserted INTEGER,
    status        TEXT
);

-- Output projections (CLV tracking + backtest)
CREATE TABLE IF NOT EXISTS projections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT NOT NULL,
    run_ts      TEXT NOT NULL,
    player_id   INTEGER REFERENCES players(player_id),
    player_name TEXT NOT NULL,
    team_id     INTEGER REFERENCES teams(team_id),
    opp_team_id INTEGER REFERENCES teams(team_id),
    game_id     TEXT    REFERENCES games(game_id),
    role_tier   TEXT,
    proj_min    REAL,
    proj_pts    REAL,   proj_pts_p25  REAL, proj_pts_p75  REAL,
    proj_reb    REAL,   proj_reb_p25  REAL, proj_reb_p75  REAL,
    proj_ast    REAL,   proj_ast_p25  REAL, proj_ast_p75  REAL,
    proj_fg3m   REAL,   proj_fg3m_p25 REAL, proj_fg3m_p75 REAL,
    proj_stl    REAL,
    proj_blk    REAL,
    proj_tov    REAL,
    injury_status      TEXT,
    pace_factor        REAL,
    matchup_factor_pts REAL,
    matchup_factor_reb REAL,
    matchup_factor_ast REAL,
    source      TEXT DEFAULT 'custom',
    dk_std      REAL,
    UNIQUE(run_date, player_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_proj_run    ON projections(run_date);
CREATE INDEX IF NOT EXISTS idx_proj_player ON projections(player_id, run_date);
"""


# ---------------------------------------------------------------------------
# DB HELPERS
# ---------------------------------------------------------------------------

def get_conn(db_path=DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 20000")   # 20s — prevents "database is locked" under contention
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = get_conn(db_path)
    conn.executescript(_DDL)
    conn.commit()
    log.info("DB initialised at %s", db_path)
    return conn


# ---------------------------------------------------------------------------
# NAME FOLDING (mirrors name_utils.py contract)
# ---------------------------------------------------------------------------
try:
    from name_utils import fold_name
except ImportError:
    import re as _re, unicodedata as _ud
    def fold_name(name) -> str:
        if not name: return ""
        s = _ud.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
        return _re.sub(r"[^a-z\s]", "", s.lower()).strip()


# ---------------------------------------------------------------------------
# NBA_API HELPERS
# ---------------------------------------------------------------------------

def _nba_api_call(endpoint_cls, **kwargs):
    """Call nba_api endpoint with retry + rate-limit sleep."""
    for attempt in range(_API_RETRY_MAX):
        try:
            resp = endpoint_cls(**kwargs, timeout=60)
            time.sleep(_API_SLEEP)
            return resp.get_data_frames()[0]
        except Exception as exc:
            wait = _API_RETRY_BACKOFF[min(attempt, len(_API_RETRY_BACKOFF) - 1)]
            log.warning("nba_api %s attempt %d: %s — retry in %ds",
                        endpoint_cls.__name__, attempt + 1, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"nba_api {endpoint_cls.__name__} failed after {_API_RETRY_MAX} attempts")


def _already_pulled(conn, season: str, ep: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM pull_log WHERE season=? AND endpoint=? AND status='ok'",
        (season, ep)
    ).fetchone() is not None


def _log_pull(conn, season: str, ep: str, rows: int, status: str = "ok"):
    conn.execute("INSERT INTO pull_log(season,endpoint,rows_upserted,status) VALUES(?,?,?,?)",
                 (season, ep, rows, status))
    conn.commit()


def _safe_int(v) -> Optional[int]:
    try: return int(v) if pd.notna(v) else None
    except: return None

def _safe_float(v) -> Optional[float]:
    try: return float(v) if pd.notna(v) else None
    except: return None


# ---------------------------------------------------------------------------
# STATIC TEAMS SEED
# ---------------------------------------------------------------------------

def _seed_teams(conn) -> None:
    from nba_api.stats.static import teams as nba_static
    rows = [(t["id"], t["abbreviation"], t["full_name"], t["city"])
            for t in nba_static.get_teams()]
    conn.executemany(
        "INSERT OR IGNORE INTO teams(team_id,abbreviation,name,city) VALUES(?,?,?,?)", rows)
    conn.commit()
    log.info("Teams seeded: %d", len(rows))


# ---------------------------------------------------------------------------
# PLAYER GAME LOGS PULL
# ---------------------------------------------------------------------------

def pull_player_game_logs(conn, season: str,
                          season_type: str = "Regular Season",
                          force: bool = False) -> int:
    """Pull all player box scores for one season via a single nba_api call."""
    from nba_api.stats.endpoints import PlayerGameLogs

    ep = f"PlayerGameLogs_{season_type.replace(' ', '')}"
    if not force and _already_pulled(conn, season, ep):
        log.info("  [skip] %s %s already pulled", season, season_type)
        return 0

    log.info("Pulling PlayerGameLogs %s %s ...", season, season_type)
    era = SEASON_ERA_WEIGHTS.get(season, 0.0)

    df = _nba_api_call(PlayerGameLogs,
                       season_nullable=season,
                       season_type_nullable=season_type)
    if df.empty:
        log.warning("  No data for %s %s", season, season_type)
        _log_pull(conn, season, ep, 0, "partial")
        return 0

    log.info("  %d rows fetched", len(df))
    df["GAME_DATE"] = df["GAME_DATE"].apply(lambda x: str(x)[:10])
    df["MIN"] = pd.to_numeric(df["MIN"], errors="coerce").fillna(0.0)

    # upsert players
    for _, r in df.drop_duplicates("PLAYER_ID").iterrows():
        conn.execute(
            "INSERT INTO players(player_id,name,name_key,team_id) VALUES(?,?,?,?) "
            "ON CONFLICT(player_id) DO UPDATE SET name=excluded.name,"
            "name_key=excluded.name_key,team_id=excluded.team_id,"
            "updated_at=datetime('now')",
            (int(r["PLAYER_ID"]), r["PLAYER_NAME"],
             fold_name(r["PLAYER_NAME"]), int(r["TEAM_ID"])))

    # build home/away per game_id
    # "vs." in MATCHUP -> that team is home;  "@" -> away
    home_away: Dict[str, Tuple] = {}
    game_dates: Dict[str, str] = {}
    for gid, grp in df.groupby("GAME_ID"):
        gid = str(gid)
        game_dates[gid] = grp["GAME_DATE"].iloc[0]
        hr = grp[grp["MATCHUP"].str.contains(r"vs\.", regex=True)]
        ar = grp[grp["MATCHUP"].str.contains("@", regex=False)]
        h = int(hr["TEAM_ID"].iloc[0]) if not hr.empty else None
        a = int(ar["TEAM_ID"].iloc[0]) if not ar.empty else None
        home_away[gid] = (h, a)

    # upsert games
    for gid, (h, a) in home_away.items():
        conn.execute(
            "INSERT INTO games(game_id,game_date,home_team_id,away_team_id,"
            "season,season_type,era_weight) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(game_id) DO NOTHING",
            (gid, game_dates[gid], h, a, season, season_type, era))

    # upsert player_game_stats
    n = 0
    for _, r in df.iterrows():
        fga = _safe_int(r.get("FGA"))
        fta = _safe_int(r.get("FTA"))
        pts = _safe_int(r.get("PTS"))
        denom = 2 * ((fga or 0) + 0.44 * (fta or 0))
        ts = round(pts / denom, 4) if (pts is not None and denom > 0) else None

        conn.execute(
            "INSERT INTO player_game_stats("
            "game_id,player_id,team_id,"
            "min,fgm,fga,fg3m,fg3a,ftm,fta,"
            "oreb,dreb,reb,ast,stl,blk,tov,pf,pts,"
            "plus_minus,ts_pct) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(game_id,player_id) DO UPDATE SET "
            "min=excluded.min,pts=excluded.pts,reb=excluded.reb,"
            "ast=excluded.ast,fg3m=excluded.fg3m,stl=excluded.stl,"
            "blk=excluded.blk,tov=excluded.tov,ts_pct=excluded.ts_pct",
            (str(r["GAME_ID"]), int(r["PLAYER_ID"]), int(r["TEAM_ID"]),
             _safe_float(r.get("MIN")),
             _safe_int(r.get("FGM")), fga,
             _safe_int(r.get("FG3M")), _safe_int(r.get("FG3A")),
             _safe_int(r.get("FTM")), _safe_int(r.get("FTA")),
             _safe_int(r.get("OREB")), _safe_int(r.get("DREB")),
             _safe_int(r.get("REB")), _safe_int(r.get("AST")),
             _safe_int(r.get("STL")), _safe_int(r.get("BLK")),
             _safe_int(r.get("TOV")), _safe_int(r.get("PF")),
             pts, _safe_float(r.get("PLUS_MINUS")), ts))
        n += 1

    conn.commit()
    _compute_starter_flags(conn, season)
    _log_pull(conn, season, ep, n)
    log.info("  %s %s done — %d rows", season, season_type, n)
    return n


def _compute_starter_flags(conn, season: str) -> None:
    """Flag top-5 MIN players per (game_id, team_id) as starters (~90% accurate)."""
    log.info("  Computing starter flags for %s ...", season)
    conn.execute(
        "UPDATE player_game_stats SET starter_flag=0 "
        "WHERE game_id IN (SELECT game_id FROM games WHERE season=?)", (season,))
    conn.execute(
        "UPDATE player_game_stats SET starter_flag=1 WHERE id IN ("
        "  SELECT pgs.id FROM player_game_stats pgs"
        "  JOIN games g ON g.game_id=pgs.game_id WHERE g.season=?"
        "  AND pgs.min IS NOT NULL"
        "  AND (SELECT COUNT(*) FROM player_game_stats p2"
        "       WHERE p2.game_id=pgs.game_id AND p2.team_id=pgs.team_id"
        "       AND (p2.min>pgs.min OR (p2.min=pgs.min AND p2.id<pgs.id))) < 5)",
        (season,))
    conn.commit()


# ---------------------------------------------------------------------------
# TEAM ADVANCED STATS
# ---------------------------------------------------------------------------

def pull_team_advanced(conn, season: str,
                       season_type: str = "Regular Season",
                       force: bool = False) -> int:
    """Pull team pace + off/def ratings from LeagueDashTeamStats Advanced."""
    from nba_api.stats.endpoints import LeagueDashTeamStats

    ep = f"TeamAdvanced_{season_type.replace(' ', '')}"
    if not force and _already_pulled(conn, season, ep):
        log.info("  [skip] TeamAdvanced %s already pulled", season)
        return 0

    log.info("Pulling LeagueDashTeamStats Advanced %s %s ...", season, season_type)
    df = _nba_api_call(LeagueDashTeamStats, season=season,
                       season_type_all_star=season_type,
                       measure_type_detailed_defense="Advanced",
                       per_mode_detailed="PerGame")
    if df.empty:
        _log_pull(conn, season, ep, 0, "partial")
        return 0

    n = 0
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO team_season_stats(team_id,season,season_type,pace,off_rtg,def_rtg,net_rtg)"
            " VALUES(?,?,?,?,?,?,?)"
            " ON CONFLICT(team_id,season,season_type) DO UPDATE SET"
            " pace=excluded.pace,off_rtg=excluded.off_rtg,"
            " def_rtg=excluded.def_rtg,net_rtg=excluded.net_rtg",
            (int(r["TEAM_ID"]), season, season_type,
             float(r.get("PACE") or 0), float(r.get("OFF_RATING") or 0),
             float(r.get("DEF_RATING") or 0), float(r.get("NET_RATING") or 0)))
        n += 1
    conn.commit()
    _log_pull(conn, season, ep, n)
    log.info("  TeamAdvanced %s done — %d rows", season, n)
    return n


# ---------------------------------------------------------------------------
# DEFENSIVE SPLITS MATERIALISATION
# ---------------------------------------------------------------------------

def compute_defensive_splits(conn, seasons: Optional[List[str]] = None) -> None:
    """Pre-compute matchup ratios per (opp_team, season, position_group, stat).

    ratio = (avg stat/36 allowed to pos_group) / (league avg stat/36 for pos_group)
    Clipped to [0.80, 1.20].  Used by nba_projector as matchup_factor.
    """
    if seasons is None:
        seasons = DEFAULT_SEASONS
    log.info("Computing defensive splits for: %s", seasons)
    ph = ",".join("?" * len(seasons))

    df = pd.read_sql_query(
        f"SELECT pgs.game_id, pgs.player_id, pgs.team_id AS ptid, pgs.min,"
        f" pgs.pts,pgs.reb,pgs.ast,pgs.fg3m,pgs.fg3a,pgs.stl,pgs.blk,pgs.tov,"
        f" g.season,g.home_team_id,g.away_team_id,p.position"
        f" FROM player_game_stats pgs"
        f" JOIN games g   ON g.game_id=pgs.game_id"
        f" JOIN players p ON p.player_id=pgs.player_id"
        f" WHERE g.season IN ({ph}) AND pgs.min>=5",
        conn, params=seasons)

    if df.empty:
        log.warning("No game data for splits — run --pull first")
        return

    df["opp_team_id"] = df.apply(
        lambda r: r["away_team_id"] if r["ptid"] == r["home_team_id"]
                  else r["home_team_id"], axis=1)
    df["pg"] = df["position"].apply(_position_group)

    for stat in _DEF_STATS:
        df[f"{stat}_p36"] = (df[stat].fillna(0) / df["min"].clip(lower=1)) * 36

    n = 0
    for season in seasons:
        sdf = df[df["season"] == season]
        for pg in _POS_GROUPS:
            pgdf = sdf[sdf["pg"] == pg]
            if pgdf.empty:
                continue
            for stat in _DEF_STATS:
                col = f"{stat}_p36"
                league_avg = pgdf[col].mean()
                if pd.isna(league_avg) or league_avg == 0:
                    continue
                agg = (pgdf.groupby("opp_team_id")[col]
                           .agg(["mean", "count"]).reset_index())
                agg.columns = ["team_id", "avg", "cnt"]
                agg = agg[agg["cnt"] >= MIN_SPLIT_GAMES]  # M8: skip 1-4 game samples (outlier ratios)
                for _, row in agg.iterrows():
                    ratio = max(_CLIP_LO, min(_CLIP_HI, float(row["avg"]) / league_avg))
                    conn.execute(
                        "INSERT INTO team_def_splits"
                        "(team_id,season,position_group,stat,avg_allowed,league_avg,ratio,games_sample)"
                        " VALUES(?,?,?,?,?,?,?,?)"
                        " ON CONFLICT(team_id,season,position_group,stat) DO UPDATE SET"
                        " avg_allowed=excluded.avg_allowed,league_avg=excluded.league_avg,"
                        " ratio=excluded.ratio,games_sample=excluded.games_sample",
                        (int(row["team_id"]), season, pg, stat,
                         float(row["avg"]), float(league_avg),
                         round(ratio, 4), int(row["cnt"])))
                    n += 1
    conn.commit()
    log.info("Defensive splits done — %d rows", n)


# ---------------------------------------------------------------------------
# FULL PULL ORCHESTRATOR
# ---------------------------------------------------------------------------

def pull_all(seasons: Optional[List[str]] = None,
             reset: bool = False,
             season_types: Optional[List[str]] = None,
             db_path: Path = DB_PATH) -> None:
    if seasons is None:
        seasons = DEFAULT_SEASONS
    if season_types is None:
        season_types = ["Regular Season", "Playoffs"]

    conn = init_db(db_path)
    if reset:
        log.warning("--reset: wiping all data")
        conn.executescript(
            "DELETE FROM projections; DELETE FROM team_def_splits;"
            " DELETE FROM team_season_stats; DELETE FROM player_game_stats;"
            " DELETE FROM games; DELETE FROM players; DELETE FROM pull_log;")
        conn.commit()

    _seed_teams(conn)
    total = 0
    for season in seasons:
        if SEASON_ERA_WEIGHTS.get(season, 0) == 0:
            log.info("Skipping %s (era_weight=0)", season)
            continue
        log.info("=== %s (era=%.2f) ===", season, SEASON_ERA_WEIGHTS[season])
        for stype in season_types:
            try:
                total += pull_player_game_logs(conn, season, stype)
            except Exception as exc:
                log.error("Error %s %s: %s", season, stype, exc)
        try:
            pull_team_advanced(conn, season)
        except Exception as exc:
            log.error("Error TeamAdvanced %s: %s", season, exc)

    # Pull positions for the most recent season (height-based inference)
    try:
        pull_player_positions(conn, seasons[-1])
    except Exception as exc:
        log.warning("Position pull failed (non-fatal): %s", exc)

    compute_defensive_splits(conn, [s for s in seasons if SEASON_ERA_WEIGHTS.get(s, 0) > 0])
    log.info("Pull complete — total player-game rows: %d", total)
    conn.close()


# ---------------------------------------------------------------------------
# QUERY API  (called by nba_projector.py)
# ---------------------------------------------------------------------------

def get_player_recent_games(player_id: int, before_date: str,
                             n_games: int = 20,
                             season_filter: Optional[str] = None,
                             min_minutes: float = 5.0,
                             db_path: Path = DB_PATH) -> pd.DataFrame:
    """Last n_games box-score rows for player, newest first.

    Includes era_weight for EWMA decay.  Excludes DNP games (min < min_minutes).
    """
    conn = get_conn(db_path)
    sc = "AND g.season = :season" if season_filter else ""
    # Join team game totals so caller can compute USG% per game.
    # L6: also join a per-game total-pts subquery to derive final_margin
    # (abs difference between the two teams' total pts).  Used by
    # compute_availability_weights() for the blowout-proxy garbage-time filter.
    try:
        df = pd.read_sql_query(
            f"SELECT pgs.game_id,g.game_date,g.season,g.era_weight,"
            f" pgs.team_id,pgs.min,pgs.pts,pgs.reb,pgs.ast,pgs.fg3m,"
            f" pgs.stl,pgs.blk,pgs.tov,pgs.fgm,pgs.fga,pgs.fg3a,"
            f" pgs.ftm,pgs.fta,pgs.oreb,pgs.dreb,"
            f" pgs.plus_minus,pgs.ts_pct,pgs.starter_flag,"
            f" tm.tm_fga,tm.tm_fta,tm.tm_tov,tm.tm_min,"
            f" ABS(COALESCE(scr.s1,0) - COALESCE(scr.s2,0)) AS game_margin"
            f" FROM player_game_stats pgs"
            f" JOIN games g ON g.game_id=pgs.game_id"
            f" JOIN ("
            f"   SELECT game_id,team_id,"
            f"          SUM(fga) AS tm_fga, SUM(fta) AS tm_fta,"
            f"          SUM(tov) AS tm_tov, SUM(min) AS tm_min"
            f"   FROM player_game_stats GROUP BY game_id,team_id"
            f" ) tm ON tm.game_id=pgs.game_id AND tm.team_id=pgs.team_id"
            f" LEFT JOIN ("
            f"   SELECT game_id,"
            f"          MAX(CASE WHEN rn=1 THEN team_pts END) AS s1,"
            f"          MAX(CASE WHEN rn=2 THEN team_pts END) AS s2"
            f"   FROM ("
            f"     SELECT game_id, team_id, SUM(pts) AS team_pts,"
            f"            ROW_NUMBER() OVER (PARTITION BY game_id"
            f"                               ORDER BY team_id) AS rn"
            f"     FROM player_game_stats GROUP BY game_id,team_id"
            f"   ) GROUP BY game_id"
            f" ) scr ON scr.game_id=pgs.game_id"
            f" WHERE pgs.player_id=:pid AND g.game_date<:before"
            f" AND pgs.min>=:mm {sc}"
            f" ORDER BY g.game_date DESC LIMIT :n",
            conn,
            params={"pid": player_id, "before": before_date,
                    "mm": min_minutes, "season": season_filter or "", "n": n_games})
    finally:
        conn.close()  # C2-001: always close — prevents leak on pd.read_sql_query exception
    return df


def get_team_shooting_stats(team_id: int, season: str,
                             db_path: Path = DB_PATH) -> dict:
    """Season-average shooting + rebound stats for a team.

    Returns:
        fga_per_game  — avg FGA per game
        fg_pct        — FGM / FGA (season)
        oreb_per_game — avg OREB per game
        dreb_per_game — avg DREB per game

    Used by compute_reb_rates() to compute available-rebound denominators.
    Falls back to league averages if insufficient data.
    """
    conn = get_conn(db_path)
    df = pd.read_sql_query(
        """
        SELECT
            SUM(pgs.fga)  AS fga,
            SUM(pgs.fgm)  AS fgm,
            SUM(pgs.oreb) AS oreb,
            SUM(pgs.dreb) AS dreb,
            COUNT(DISTINCT pgs.game_id) AS n_games
        FROM player_game_stats pgs
        JOIN games g ON g.game_id = pgs.game_id
        WHERE pgs.team_id = :team_id
          AND g.season    = :season
          AND g.season_type = 'Regular Season'
        """,
        conn,
        params={"team_id": team_id, "season": season},
    )
    conn.close()

    # League-average fallbacks (2024-25 calibrated)
    _DEFAULTS = {
        "fga_per_game":  88.0,
        "fg_pct":        0.468,
        "oreb_per_game": 10.5,
        "dreb_per_game": 33.5,
    }
    if df.empty:
        return dict(_DEFAULTS)
    row = df.iloc[0]
    n = int(row["n_games"] or 0)
    if n < 5:
        return dict(_DEFAULTS)
    fga = float(row["fga"] or 0)
    fgm = float(row["fgm"] or 0)
    return {
        "fga_per_game":  fga / n,
        "fg_pct":        min(fgm / max(fga, 1.0), 0.99),
        "oreb_per_game": float(row["oreb"] or 0) / n,
        "dreb_per_game": float(row["dreb"] or 0) / n,
    }


def get_team_tov_rate(team_id: int, season: str,
                      db_path: Path = DB_PATH) -> float:
    """Season-average team TOV rate (turnovers / possession).

    tov_rate = tov_per_game / pace.
    Falls back to league average (0.136) if insufficient data.
    Calibrated from 2024-25 DB: league avg = 0.136 (2026-05-01).
    """
    _LEAGUE_AVG = 0.136
    conn = get_conn(db_path)
    df = pd.read_sql_query(
        """
        SELECT
            SUM(pgs.tov)                AS total_tov,
            COUNT(DISTINCT pgs.game_id) AS n_games
        FROM player_game_stats pgs
        JOIN games g ON g.game_id = pgs.game_id
        WHERE pgs.team_id   = :team_id
          AND g.season       = :season
          AND g.season_type  = 'Regular Season'
        """,
        conn,
        params={"team_id": team_id, "season": season},
    )
    conn.close()
    if df.empty:
        return _LEAGUE_AVG
    row = df.iloc[0]
    n = int(row["n_games"] or 0)
    if n < 5:
        return _LEAGUE_AVG
    tov_per_game = float(row["total_tov"] or 0) / n
    pace = get_team_pace(team_id, season, "Regular Season", db_path)
    if pace <= 0:
        return _LEAGUE_AVG
    return float(max(0.05, min(0.30, tov_per_game / pace)))


def get_team_rim_attempt_rate(team_id: int, season: str,
                              db_path: Path = DB_PATH) -> float:
    """Season-average opponent non-3pt FGA per game (proxy for rim/paint attempts).

    rim_attempt_rate = (team.fga - team.fg3a) / n_games

    Used as the BLK opportunity multiplier: teams that attack the paint more
    create more shot-blocking chances for rim protectors.

    Proxy rationale: true "restricted area" attempt data is not available in
    player_game_stats; (fga - fg3a) includes mid-range as well as rim attempts
    but is a stable proxy for drive-frequency across teams.

    Falls back to league average (56.0) if insufficient data.
    League avg calibrated from 2024-25 NBA averages:
        ~85 FGA/game, ~29 3PA/game => ~56 non-3pt FGA/game.
    """
    _LEAGUE_AVG = 56.0  # non-3pt FGA per game, 2024-25 league average
    conn = get_conn(db_path)
    df = pd.read_sql_query(
        """
        SELECT
            SUM(pgs.fga  - pgs.fg3a)    AS total_non3_fga,
            COUNT(DISTINCT pgs.game_id) AS n_games
        FROM player_game_stats pgs
        JOIN games g ON g.game_id = pgs.game_id
        WHERE pgs.team_id   = :team_id
          AND g.season       = :season
          AND g.season_type  = 'Regular Season'
        """,
        conn,
        params={"team_id": team_id, "season": season},
    )
    conn.close()
    if df.empty:
        return _LEAGUE_AVG
    row = df.iloc[0]
    n = int(row["n_games"] or 0)
    if n < 5:
        return _LEAGUE_AVG
    non3_fga_per_game = float(row["total_non3_fga"] or 0) / n
    # Sanity clip: no team averages below 35 or above 80 non-3pt FGA/game
    return float(max(35.0, min(80.0, non3_fga_per_game)))


def get_team_avg_fga(team_id: int, before_date: str,
                     season: str, n_games: int = 20,
                     season_type: str = "Regular Season",
                     db_path: Path = DB_PATH) -> float:
    """Team average FGA per game over last n_games (for FGA decomposition).

    M3 (May 1 2026): added season_type filter (default "Regular Season") and
    ORDER BY + LIMIT so only the most-recent n_games contribute, not stale
    early-season data.  Playoff games have different pace/shot-selection and
    must not contaminate regular-season averages.
    """
    conn = get_conn(db_path)
    row = conn.execute(
        """
        SELECT AVG(team_fga) FROM (
            SELECT SUM(pgs.fga) AS team_fga
            FROM player_game_stats pgs
            JOIN games g ON g.game_id = pgs.game_id
            WHERE pgs.team_id = ? AND g.season = ?
              AND g.season_type = ?
              AND g.game_date < ?
            GROUP BY pgs.game_id
            ORDER BY g.game_date DESC
            LIMIT ?
        )
        """,
        (team_id, season, season_type, before_date, n_games)
    ).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else 85.0  # league-avg fallback


def get_player_career_avg_minutes(
    player_id: int,
    current_season: str,
    db_path: Path = DB_PATH,
    min_games: int = 10,
) -> Optional[float]:
    """Return the player's career average minutes per game, excluding the current season.

    Uses all prior seasons in the DB where the player played >= min_games.
    Returns None if no qualifying history exists (true first-year / data gap).
    Used by the cold-start pipeline to replace the flat 16.0 MPG prior with an
    empirical per-player prior when available (task #2, 2026-05-02).
    """
    conn = get_conn(db_path)
    try:
        row = conn.execute(
            """
            SELECT AVG(pgs.min)
            FROM player_game_stats pgs
            JOIN games g ON g.game_id = pgs.game_id
            WHERE pgs.player_id = ?
              AND g.season != ?
              AND pgs.min >= 5
            GROUP BY pgs.player_id
            HAVING COUNT(*) >= ?
            """,
            (player_id, current_season, min_games),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        log.warning("H19: no career history for player_id=%s (season=%s, min_games=%s) — cold_start will use flat prior", player_id, current_season, min_games)
    return float(row[0]) if row else None


def get_player_career_game_count(
    player_id: int,
    current_season: str,
    db_path: Path = DB_PATH,
) -> tuple[int, float | None]:  # L2: tightened return type hint
    """Return (n_career_games, career_avg_min_raw) across ALL seasons excluding current.

    n_career_games: total qualifying game count (min >= 5) in all prior seasons.
    career_avg_min_raw: raw average minutes across those games (None if zero games).

    Qualifying threshold: min >= 5 (same as get_player_recent_games default).
    A player with n_career_games == 0 has no qualifying appearances in the DB —
    they are classified as 'taxi' regardless of last_appearance_days.

    Used by R7 (Research Brief 7) cold-start sub-type classification:
      - taxi:          n_career_games == 0  (never appeared in DB)
      - returner:      n_career_games >= 1  AND last_appearance_days >= 180
      - new_acquisition: n_career_games >= 1  AND last_appearance_days < 180

    See also: get_player_last_appearance_days() — provides the days component.
    """
    conn = get_conn(db_path)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*), AVG(pgs.min)
            FROM player_game_stats pgs
            JOIN games g ON g.game_id = pgs.game_id
            WHERE pgs.player_id = ?
              AND g.season != ?
              AND pgs.min >= 5
            """,
            (player_id, current_season),
        ).fetchone()
    finally:
        conn.close()
    n = int(row[0]) if row else 0
    avg_min = float(row[1]) if row and row[1] is not None else None
    return n, avg_min


def get_player_last_appearance_days(
    player_id: int,
    before_date: str,
    db_path: Path = DB_PATH,
) -> Optional[int]:
    """Return the number of days since the player's most recent DB game appearance.

    before_date: ISO date string (YYYY-MM-DD) — only games strictly before this
    date are considered (i.e. exclude today's scheduled game).
    Returns None if the player has no prior appearances in the DB.

    Used by R7 (Research Brief 7) to classify returner vs new_acquisition:
      - >= 180 days gap => returner (injury return / G-League call-up)
      - <  180 days gap => new_acquisition (recent trade, waiver, or call-up)
    """
    conn = get_conn(db_path)
    try:
        row = conn.execute(
            """
            SELECT MAX(g.game_date)
            FROM player_game_stats pgs
            JOIN games g ON g.game_id = pgs.game_id
            WHERE pgs.player_id = ?
              AND g.game_date < ?
              AND pgs.min >= 5
            """,
            (player_id, before_date),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    from datetime import date
    try:  # C4: guard against malformed date strings in DB
        last_date = date.fromisoformat(row[0])
        ref_date = date.fromisoformat(before_date)
    except ValueError as e:
        log.warning("get_player_last_appearance_days: bad date string (player_id=%s): %s", player_id, e)
        return None
    return (ref_date - last_date).days


def get_player_season_game_count(player_id: int, season: str,
                                  team_id: Optional[int] = None,
                                  db_path: Path = DB_PATH) -> int:
    """Games played by player this season.  < 10 => cold-start pipeline."""
    conn = get_conn(db_path)
    tc = "AND pgs.team_id=?" if team_id else ""
    params: list = [player_id, season]
    if team_id:
        params.append(team_id)
    row = conn.execute(
        f"SELECT COUNT(*) FROM player_game_stats pgs"
        f" JOIN games g ON g.game_id=pgs.game_id"
        f" WHERE pgs.player_id=? AND g.season=? AND pgs.min>=5 {tc}",
        params).fetchone()
    conn.close()
    return int(row[0]) if row else 0


def get_player_trade_context(
    player_id: int,
    season: str,
    current_team_id: int,
    before_date: str,
    db_path: Path = DB_PATH,
) -> Optional[dict]:
    """Detect if a player changed teams this season and return prior-team context.

    Returns a dict if the player has < 7 games on the current team AND played
    for a different team earlier this season:
        {
            "prev_team_id":     int,
            "games_on_new_team": int,   # games played for current_team_id (min>=5)
            "prev_team_df":     pd.DataFrame,  # recent games on prior team (n<=20)
        }
    Returns None if no trade is detected or if player has >= 7 new-team games
    (blend window closed).
    """
    _BLEND_WINDOW = 6  # applies blend for games 1-6 on new team

    conn = get_conn(db_path)
    try:  # H2: wrap entire body so conn is always closed
        # Games on current team this season (qualifying minutes threshold: 5)
        row_new = conn.execute(
            "SELECT COUNT(*) FROM player_game_stats pgs"
            " JOIN games g ON g.game_id=pgs.game_id"
            " WHERE pgs.player_id=? AND g.season=? AND pgs.team_id=?"
            " AND pgs.min>=5 AND g.game_date<?",
            (player_id, season, current_team_id, before_date),
        ).fetchone()
        games_on_new_team = int(row_new[0]) if row_new else 0

        if games_on_new_team > _BLEND_WINDOW or games_on_new_team == 0:
            return None  # outside blend window or no games yet

        # Find most recent prior team this season (different from current_team_id)
        row_prev = conn.execute(
            "SELECT pgs.team_id FROM player_game_stats pgs"
            " JOIN games g ON g.game_id=pgs.game_id"
            " WHERE pgs.player_id=? AND g.season=? AND pgs.team_id!=?"
            " AND pgs.min>=5 AND g.game_date<?"
            " ORDER BY g.game_date DESC LIMIT 1",
            (player_id, season, current_team_id, before_date),
        ).fetchone()

        if row_prev is None:
            return None  # no prior team this season

        prev_team_id = int(row_prev[0])

        # Fetch last 20 qualifying games on prior team (for rate estimation)
        prev_df = pd.read_sql_query(
            "SELECT pgs.*,g.game_date,g.era_weight"
            " FROM player_game_stats pgs"
            " JOIN games g ON g.game_id=pgs.game_id"
            " WHERE pgs.player_id=? AND pgs.team_id=? AND pgs.min>=5"
            " ORDER BY g.game_date DESC LIMIT 20",
            conn,
            params=(player_id, prev_team_id),
        )
    finally:
        conn.close()

    return {
        "prev_team_id":      prev_team_id,
        "games_on_new_team": games_on_new_team,
        "prev_team_df":      prev_df,
    }


def get_team_typical_mpg(
    team_id: int,
    season: str,
    before_date: str,
    min_mpg_threshold: float = 12.0,
    db_path: Path = DB_PATH,
) -> Dict[int, float]:
    """Return {player_id: avg_min} for players who averaged ≥ min_mpg_threshold
    minutes for team_id in the given season before before_date.

    Minimum 5 qualifying games (min >= 5) required to appear.
    Used by L4 availability weighting to identify "key" teammates whose
    absence inflates/deflates the target player's rate estimates.
    """
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT pgs.player_id, AVG(pgs.min) AS avg_min"
        " FROM player_game_stats pgs"
        " JOIN games g ON g.game_id = pgs.game_id"
        " WHERE pgs.team_id = ? AND g.season = ? AND g.game_date < ?"
        " AND pgs.min >= 5"
        " GROUP BY pgs.player_id"
        " HAVING COUNT(*) >= 5 AND AVG(pgs.min) >= ?",
        (team_id, season, before_date, min_mpg_threshold),
    ).fetchall()
    conn.close()
    return {int(r[0]): float(r[1]) for r in rows}


def get_team_game_participants(
    team_id: int,
    game_ids: List[str],
    db_path: Path = DB_PATH,
) -> Dict[str, set]:
    """Return {game_id: set(player_ids)} for players who played ≥ 5 min
    for team_id in each of the given game_ids.

    Used by L4 availability weighting to check which key teammates were
    present in each training game.
    """
    if not game_ids:
        return {}
    conn = get_conn(db_path)
    placeholders = ",".join("?" * len(game_ids))
    rows = conn.execute(
        f"SELECT pgs.game_id, pgs.player_id FROM player_game_stats pgs"
        f" WHERE pgs.team_id = ? AND pgs.game_id IN ({placeholders})"
        f" AND pgs.min >= 5",
        (team_id, *game_ids),
    ).fetchall()
    conn.close()
    result: Dict[str, set] = {gid: set() for gid in game_ids}
    for gid, pid in rows:
        result[str(gid)].add(int(pid))
    return result


_LEAGUE_AVG_PACE_FALLBACK = 100.22  # 2024-25 full-season NBA pace (R5, Research Brief 7)
                                     # H1: was stale 99.5; kept in sync with nba_projector.LEAGUE_AVG_PACE


def get_team_pace(team_id: int, season: str,
                  season_type: str = "Regular Season",
                  db_path: Path = DB_PATH) -> float:
    """Team pace (possessions/48). Falls back to _LEAGUE_AVG_PACE_FALLBACK if not found."""
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT pace FROM team_season_stats"
        " WHERE team_id=? AND season=? AND season_type=?",
        (team_id, season, season_type)).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else _LEAGUE_AVG_PACE_FALLBACK


def get_team_def_ratio(opp_team_id: int, position_group: str,
                        stat: str, season: str,
                        db_path: Path = DB_PATH) -> float:
    """Matchup factor [0.80, 1.20]. 1.0 = neutral (fallback)."""
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT ratio FROM team_def_splits"
        " WHERE team_id=? AND season=? AND position_group=? AND stat=?",
        (opp_team_id, season, position_group, stat)).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else 1.0


def get_player_b2b_context(player_id: int, game_date,
                            db_path: Path = DB_PATH) -> dict:
    """Return dict: is_b2b, days_rest, last_game_date, last_game_min."""
    if not isinstance(game_date, str):
        game_date = str(game_date)
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT g.game_date,pgs.min FROM player_game_stats pgs"
        " JOIN games g ON g.game_id=pgs.game_id"
        " WHERE pgs.player_id=? AND g.game_date<? AND pgs.min>=5"
        " ORDER BY g.game_date DESC LIMIT 1",
        (player_id, game_date)).fetchone()
    conn.close()
    if not row:
        return {"is_b2b": False, "days_rest": 7,
                "last_game_date": None, "last_game_min": 0.0}
    try:
        days = (datetime.strptime(game_date, "%Y-%m-%d")
                - datetime.strptime(row[0], "%Y-%m-%d")).days - 1
    except ValueError:
        days = 3
    return {"is_b2b": days == 0, "days_rest": max(0, days),
            "last_game_date": row[0], "last_game_min": float(row[1] or 0)}


def get_all_active_players(before_date: str, min_recent_games: int = 3,
                            db_path: Path = DB_PATH) -> pd.DataFrame:
    """Players with recent history — projection candidate pool."""
    conn = get_conn(db_path)
    df = pd.read_sql_query(
        "SELECT p.player_id,p.name,p.name_key,p.position,p.team_id"
        " FROM players p"
        " WHERE (SELECT COUNT(*) FROM player_game_stats pgs"
        "        JOIN games g ON g.game_id=pgs.game_id"
        "        WHERE pgs.player_id=p.player_id"
        "        AND g.game_date<:before AND pgs.min>=5) >= :mg",
        conn, params={"before": before_date, "mg": min_recent_games})
    conn.close()
    return df


def seed_scheduled_games(
    game_date: str,
    season: str = CURRENT_SEASON,
    db_path: Path = DB_PATH,
) -> int:
    """Seed today's scheduled games from ScoreboardV2 before games are played.

    Inserts upcoming games into the games table using ON CONFLICT DO NOTHING so
    completed games already in the DB are never overwritten.  Returns the number
    of games newly inserted.

    Called at the start of generate_projections.py run() so the projector can
    build projections before tip-off (not just after games complete).

    Falls back gracefully if the NBA API is unreachable or returns no data.
    """
    try:
        from nba_api.stats.endpoints import ScoreboardV2
    except ImportError:
        log.warning("seed_scheduled_games: nba_api not available — skipping")
        return 0

    try:
        sb = ScoreboardV2(game_date=game_date, timeout=10)
        games_df = sb.game_header.get_data_frame()
    except Exception as exc:
        log.warning("seed_scheduled_games: API call failed for %s — %s", game_date, exc)
        return 0

    if games_df is None or games_df.empty:
        log.info("seed_scheduled_games: no games returned for %s", game_date)
        return 0

    # Determine season_type from game_id prefix: 002=Regular, 004=Playoffs, 001=Preseason
    def _season_type_from_id(gid: str) -> str:
        gid = str(gid)
        if len(gid) >= 3:
            prefix = gid[2]  # NBA game_id: 10-digit, char index 2 = type
            if prefix == "4":
                return "Playoffs"
            if prefix == "2":
                return "Regular Season"
        return "Regular Season"

    conn = get_conn(db_path)
    # Ensure teams table is populated (safe no-op if already seeded)
    try:
        _seed_teams(conn)
    except Exception:
        pass  # teams already exist

    inserted = 0
    try:
        for _, row in games_df.iterrows():
            gid        = str(row.get("GAME_ID", "")).strip()
            home_tid   = _safe_int(row.get("HOME_TEAM_ID"))
            away_tid   = _safe_int(row.get("VISITOR_TEAM_ID"))
            gdate      = str(row.get("GAME_DATE_EST", game_date))[:10]
            if not gid or home_tid is None or away_tid is None:
                continue
            stype = _season_type_from_id(gid)
            era   = 1.0  # era_weight — same default as pull_player_game_logs
            cur = conn.execute(
                "INSERT INTO games(game_id,game_date,home_team_id,away_team_id,"
                "season,season_type,era_weight) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(game_id) DO NOTHING",
                (gid, gdate, home_tid, away_tid, season, stype, era),
            )
            inserted += cur.rowcount
        conn.commit()
    except Exception as exc:
        log.warning("seed_scheduled_games: DB write failed — %s", exc)
        conn.rollback()
    finally:
        conn.close()

    if inserted:
        log.info("seed_scheduled_games: inserted %d game(s) for %s", inserted, game_date)
    else:
        log.info("seed_scheduled_games: %s — games already in DB (no new inserts)", game_date)
    return inserted


def get_games_for_date(game_date: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """All games on date with team abbreviations."""
    conn = get_conn(db_path)
    df = pd.read_sql_query(
        "SELECT g.game_id,g.game_date,g.home_team_id,g.away_team_id,"
        " th.abbreviation AS home_abbr,ta.abbreviation AS away_abbr,g.season,g.season_type"
        " FROM games g"
        " JOIN teams th ON th.team_id=g.home_team_id"
        " JOIN teams ta ON ta.team_id=g.away_team_id"
        " WHERE g.game_date=?",
        conn, params=(game_date,))
    conn.close()
    return df


def upsert_projection(conn, proj: dict) -> None:
    """Insert or replace one projection row into projections table."""
    conn.execute(
        "INSERT INTO projections(run_date,run_ts,player_id,player_name,"
        " team_id,opp_team_id,game_id,role_tier,"
        " proj_min,proj_pts,proj_pts_p25,proj_pts_p75,"
        " proj_reb,proj_reb_p25,proj_reb_p75,"
        " proj_ast,proj_ast_p25,proj_ast_p75,"
        " proj_fg3m,proj_fg3m_p25,proj_fg3m_p75,"
        " proj_stl,proj_blk,proj_tov,"
        " injury_status,pace_factor,"
        " matchup_factor_pts,matchup_factor_reb,matchup_factor_ast,"
        " source,dk_std)"
        " VALUES(:run_date,:run_ts,:player_id,:player_name,"
        " :team_id,:opp_team_id,:game_id,:role_tier,"
        " :proj_min,:proj_pts,:proj_pts_p25,:proj_pts_p75,"
        " :proj_reb,:proj_reb_p25,:proj_reb_p75,"
        " :proj_ast,:proj_ast_p25,:proj_ast_p75,"
        " :proj_fg3m,:proj_fg3m_p25,:proj_fg3m_p75,"
        " :proj_stl,:proj_blk,:proj_tov,"
        " :injury_status,:pace_factor,"
        " :matchup_factor_pts,:matchup_factor_reb,:matchup_factor_ast,"
        " :source,:dk_std)"
        " ON CONFLICT(run_date,player_id,game_id) DO UPDATE SET"
        # C5: previously missing columns — stale data persisted on re-run
        " player_name=excluded.player_name,"
        " team_id=excluded.team_id,opp_team_id=excluded.opp_team_id,"
        " role_tier=excluded.role_tier,"
        " proj_min=excluded.proj_min,"
        " proj_pts=excluded.proj_pts,proj_pts_p25=excluded.proj_pts_p25,proj_pts_p75=excluded.proj_pts_p75,"
        " proj_reb=excluded.proj_reb,proj_reb_p25=excluded.proj_reb_p25,proj_reb_p75=excluded.proj_reb_p75,"
        " proj_ast=excluded.proj_ast,proj_ast_p25=excluded.proj_ast_p25,proj_ast_p75=excluded.proj_ast_p75,"
        " proj_fg3m=excluded.proj_fg3m,proj_fg3m_p25=excluded.proj_fg3m_p25,proj_fg3m_p75=excluded.proj_fg3m_p75,"
        " proj_stl=excluded.proj_stl,proj_blk=excluded.proj_blk,proj_tov=excluded.proj_tov,"
        " injury_status=excluded.injury_status,pace_factor=excluded.pace_factor,"
        " matchup_factor_pts=excluded.matchup_factor_pts,"
        " matchup_factor_reb=excluded.matchup_factor_reb,"
        " matchup_factor_ast=excluded.matchup_factor_ast,"
        " source=excluded.source,dk_std=excluded.dk_std,"
        " run_ts=excluded.run_ts",
        proj)



# ---------------------------------------------------------------------------
# Status / verify
# ---------------------------------------------------------------------------

def print_status(db_path: str = DB_PATH) -> None:
    """Print row counts and pull log summary."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    tables = ["players", "teams", "games", "player_game_stats",
              "team_season_stats", "team_def_splits", "projections", "pull_log"]
    print(f"\n{'Table':<25} {'Rows':>8}")
    print("-" * 35)
    for t in tables:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            n = "ERR"
        print(f"{t:<25} {n:>8}")

    # Season breakdown from games
    print("\nGames by season:")
    rows = cur.execute(
        "SELECT season, season_type, COUNT(*) as n FROM games "
        "GROUP BY season, season_type ORDER BY season, season_type"
    ).fetchall()
    for r in rows:
        print(f"  {r[0]} {r[1]}: {r[2]} games")

    # Era weights check
    ew = cur.execute(
        "SELECT DISTINCT era_weight FROM games ORDER BY era_weight"
    ).fetchall()
    weights = [r[0] for r in ew]
    print(f"\nDistinct era_weights: {weights}")

    # Pull log tail
    print("\nPull log (last 10):")
    rows = cur.execute(
        "SELECT season, endpoint, pulled_at, rows_upserted, status "
        "FROM pull_log ORDER BY id DESC LIMIT 10"
    ).fetchall()
    for r in rows:
        print(f"  {r[0]} | {r[1]:<35} | {r[2][:16]} | {r[3]:>6} rows | {r[4]}")

    conn.close()


def verify(db_path: str = DB_PATH) -> bool:
    """Run sanity checks. Returns True if all pass."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    checks = []

    def chk(label: str, expr: bool) -> None:
        status = "PASS" if expr else "FAIL"
        checks.append((label, status))
        print(f"  [{status}] {label}")

    print("\nVerification checks:")

    n_players = cur.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    chk("players > 0", n_players > 0)

    n_teams = cur.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    chk("teams seeded (>= 30)", n_teams >= 30)

    n_games = cur.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    chk("games > 0", n_games > 0)

    n_stats = cur.execute("SELECT COUNT(*) FROM player_game_stats").fetchone()[0]
    chk("player_game_stats > 0", n_stats > 0)

    n_seasons = cur.execute("SELECT COUNT(DISTINCT season) FROM games").fetchone()[0]
    n_weights = cur.execute(
        "SELECT COUNT(DISTINCT era_weight) FROM games"
    ).fetchone()[0]
    # Only require multiple weights when multiple seasons are loaded
    chk("era_weights set", n_weights >= 1 if n_seasons <= 1 else n_weights >= 2)

    n_starters = cur.execute(
        "SELECT COUNT(*) FROM player_game_stats WHERE starter_flag=1"
    ).fetchone()[0]
    chk("starter_flag populated (> 0)", n_starters > 0)

    n_splits = cur.execute("SELECT COUNT(*) FROM team_def_splits").fetchone()[0]
    chk("team_def_splits populated", n_splits > 0)

    n_pace = cur.execute("SELECT COUNT(*) FROM team_season_stats").fetchone()[0]
    chk("team_season_stats populated", n_pace > 0)

    conn.close()
    passed = sum(1 for _, s in checks if s == "PASS")
    total = len(checks)
    print(f"\n{passed}/{total} checks passed.")
    return passed == total

def pull_player_positions(conn: sqlite3.Connection,
                          season: str = "2025-26") -> int:
    """Infer position (G/F/C) from player height and update players table.

    Uses LeagueDashPlayerBioStats (1 API call) + height thresholds:
      <= 76" -> G  |  77-80" -> F  |  >= 81" -> C
    """
    from nba_api.stats.endpoints import LeagueDashPlayerBioStats
    log.info("Pulling player positions via height inference (%s) ...", season)
    df = _nba_api_call(LeagueDashPlayerBioStats,
                      season=season,
                      season_type_all_star="Regular Season")
    if df.empty:
        log.warning("No bio data returned")
        return 0

    def _infer_pos(height_inches) -> str:
        try:
            h = float(height_inches)
        except (TypeError, ValueError):
            return "F"
        if h <= 76:
            return "G"
        if h <= 80:
            return "F"
        return "C"

    updated = 0
    for _, row in df.iterrows():
        pos = _infer_pos(row.get("PLAYER_HEIGHT_INCHES"))
        conn.execute(
            "UPDATE players SET position=? WHERE player_id=?",
            (pos, int(row["PLAYER_ID"])))
        updated += 1
    conn.commit()
    log.info("  Player positions updated: %d", updated)
    return updated

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="JonnyParlay projection DB manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python engine/projections_db.py --pull                          # pull all seasons
  python engine/projections_db.py --pull --seasons 2025-26        # one season
  python engine/projections_db.py --pull --seasons 2025-26 --season-types Playoffs
  python engine/projections_db.py --pull --reset                  # wipe + repull
  python engine/projections_db.py --recompute-splits              # rebuild splits only
  python engine/projections_db.py --verify                        # sanity checks
  python engine/projections_db.py --status                        # DB summary
        """,
    )
    parser.add_argument("--pull", action="store_true",
                        help="Pull historical data from nba_api")
    parser.add_argument("--seasons", nargs="+",
                        default=None,
                        help="Seasons to pull, e.g. 2024-25 2025-26 (default: DEFAULT_SEASONS)")
    parser.add_argument("--season-types", nargs="+",
                        default=["Regular Season", "Playoffs"],
                        dest="season_types",
                        help="Season types to pull (default: Regular Season Playoffs)")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe all data before pulling (use with --pull)")
    parser.add_argument("--force", action="store_true",
                        help="Clear pull_log for targeted seasons before pulling, "
                             "forcing a fresh fetch even if already pulled. "
                             "Use for daily playoff updates.")
    parser.add_argument("--recompute-splits", action="store_true",
                        dest="recompute_splits",
                        help="Rebuild team_def_splits from existing game stats (no API calls)")
    parser.add_argument("--verify", action="store_true",
                        help="Run sanity checks on the DB")
    parser.add_argument("--status", action="store_true",
                        help="Print DB summary (row counts, pull log)")
    parser.add_argument("--db", default=None,
                        help="Override DB path (default: data/projections.db)")
    args = parser.parse_args()

    db = Path(args.db) if args.db else DB_PATH

    if args.status:
        print_status(db)

    if args.verify:
        ok = verify(db)
        if not ok:
            sys.exit(1)

    if args.recompute_splits:
        log.info("Recomputing defensive splits...")
        conn = get_conn(db)
        compute_defensive_splits(conn)
        conn.close()
        log.info("Splits recomputed.")

    if args.pull:
        seasons = args.seasons  # None = use DEFAULT_SEASONS
        if args.force:
            # Clear pull_log for the targeted seasons+types so they re-fetch fresh data.
            # Useful for daily playoff pulls where the season is "already pulled" but
            # new games have been completed since the last pull.
            conn = get_conn(db)
            season_list = seasons if seasons else DEFAULT_SEASONS
            for s in season_list:
                for st in args.season_types:
                    ep = f"PlayerGameLogs_{st.replace(' ', '')}"
                    conn.execute("DELETE FROM pull_log WHERE season=? AND endpoint=?", (s, ep))
            conn.commit()
            conn.close()
            log.info("--force: cleared pull_log for %s / %s", season_list, args.season_types)
        pull_all(seasons=seasons, reset=args.reset,
                 season_types=args.season_types, db_path=db)

    if not any([args.pull, args.recompute_splits, args.verify, args.status]):
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _main()
