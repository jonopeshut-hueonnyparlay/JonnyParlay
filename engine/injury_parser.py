"""injury_parser.py -- NBA injury report parser + minutes redistribution.

Pulls the official NBA injury PDF via nbainjuries, maps players to IDs via
fold_name(), and returns dicts ready for run_projections():
  - injury_statuses:          {player_id: "O" | "Q" | "GTD" | "P" | ""}
  - injury_minutes_overrides: {player_id: adjusted_minutes}

Minutes redistribution: when a starter is OUT, their projected minutes are
redistributed proportionally to their team's eligible rotation players.
"""
from __future__ import annotations

import datetime
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from name_utils import fold_name
from projections_db import DB_PATH, get_conn, get_player_recent_games

log = logging.getLogger("injury_parser")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------
# Official NBA report status -> internal code + play probability
_STATUS_MAP: Dict[str, Tuple[str, float]] = {
    "out":           ("O",   0.00),
    "doubtful":      ("O",   0.10),   # treat doubtful as effectively out
    "questionable":  ("Q",   0.50),
    "game time decision": ("GTD", 0.65),
    "probable":      ("P",   0.85),
}

# ---------------------------------------------------------------------------
# P13 redistribution constants
# ---------------------------------------------------------------------------
# Fraction of an OUT player's minutes that flow to each position group.
# Rows = absent player's position group; cols = recipient group.
_POS_FLOW: Dict[str, Dict[str, float]] = {
    "G": {"G": 0.60, "F": 0.30, "C": 0.10},
    "F": {"G": 0.25, "F": 0.50, "C": 0.25},
    "C": {"G": 0.10, "F": 0.30, "C": 0.60},
}
_DEFAULT_POS_FLOW: Dict[str, float] = {"G": 0.33, "F": 0.34, "C": 0.33}

REDISTRIB_PRIMARY_SHARE = 0.50   # primary backup's share of same-pos pool
REDISTRIB_EFFICIENCY    = 0.90   # efficiency discount on incremental usage
REDISTRIB_MIN_ELIGIBLE  = 8.0    # min avg minutes to qualify as recipient
REDISTRIB_MAX_MIN       = 42.0   # hard ceiling on any player's projected minutes

def _parse_status(raw: str) -> Tuple[str, float]:
    """Map raw Current Status string to (code, play_probability)."""
    key = str(raw).strip().lower()
    for pattern, val in _STATUS_MAP.items():
        if key.startswith(pattern):
            return val
    return ("", 1.0)   # Active / unknown -> assume playing

# ---------------------------------------------------------------------------
# Report fetch -- try multiple timestamps for today's report
# ---------------------------------------------------------------------------
_REPORT_HOURS = [
    (6, 30, "AM"), (9, 0, "AM"), (10, 0, "AM"), (11, 0, "AM"),
    (1, 0, "PM"), (3, 0, "PM"), (5, 0, "PM"), (6, 30, "PM"),
]

def _build_timestamps(date: datetime.date) -> List[datetime.datetime]:
    """Build candidate timestamps for the NBA injury report on a given date."""
    candidates = []
    for h, m, meridiem in _REPORT_HOURS:
        hour24 = h if meridiem == "AM" else (h + 12 if h != 12 else 12)
        candidates.append(datetime.datetime(date.year, date.month, date.day, hour24, m))
    return candidates


def fetch_injury_report(date: Optional[datetime.date] = None) -> pd.DataFrame:
    """Fetch NBA injury report for date (default: today).

    Returns DataFrame with columns:
        player_name, team, status_raw, status_code, play_prob, game_date, matchup
    Returns empty DataFrame on failure (network blocked, no report yet, etc.).
    """
    try:
        from nbainjuries.injury import get_reportdata, check_reportvalid, gen_url
        from nbainjuries._exceptions import URLRetrievalError
    except (ImportError, Exception) as _ie:
        # Catches ImportError (package missing) and JVMNotFoundException (Java/jvm.dll
        # not installed) which jpype raises during nbainjuries __init__ import.
        log.warning("nbainjuries unavailable (%s) -- injury data skipped", type(_ie).__name__)
        return pd.DataFrame()

    if date is None:
        date = datetime.date.today()

    timestamps = list(reversed(_build_timestamps(date)))  # try latest first
    last_err = None

    for idx, ts in enumerate(timestamps):
        # Retry the 3 most recent timestamps once on transient failure (10s delay).
        max_attempts = 2 if idx < 3 else 1
        for attempt in range(max_attempts):
            try:
                if not check_reportvalid(ts):
                    break  # timestamp not valid; skip to next
                df_raw = get_reportdata(ts, return_df=True)
                if df_raw is not None and not df_raw.empty:
                    log.info("Injury report fetched for %s (ts=%s)", date, ts.strftime("%I:%M %p"))
                    return _normalise_report(df_raw)
                break  # valid timestamp but empty — move on
            except (KeyError, ValueError, TypeError, AttributeError, RuntimeError,
                    URLRetrievalError, OSError) as exc:
                # M15: catch expected parse/network errors only; let unexpected bugs propagate
                last_err = exc
                if attempt + 1 < max_attempts:
                    log.debug("Injury report fetch failed (attempt %d/%d) for ts=%s: %s — retrying in 10s",
                              attempt + 1, max_attempts, ts.strftime("%I:%M %p"), exc)
                    time.sleep(10)

    if last_err:
        log.warning("Could not fetch injury report for %s: %s", date, last_err)
    else:
        log.info("No valid injury report found for %s yet", date)
    return pd.DataFrame()


def _maybe_reverse_name(name: str) -> str:
    """Convert 'Last, First' (NBA PDF format) to 'First Last'."""
    if isinstance(name, str) and "," in name:
        last, _, first = name.partition(",")
        return f"{first.strip()} {last.strip()}"
    return name


def _normalise_report(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise raw nbainjuries DataFrame into standard schema."""
    col_map = {
        "Player Name":    "player_name",
        "Team":           "team_abbrev",
        "Current Status": "status_raw",
        "Game Date":      "game_date",
        "Matchup":        "matchup",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    needed = ["player_name", "status_raw"]
    for c in needed:
        if c not in df.columns:
            df[c] = ""

    # NBA injury PDF uses "Last, First" — convert to "First Last" before folding
    df["player_name"] = df["player_name"].apply(
        lambda x: _maybe_reverse_name(str(x)) if pd.notna(x) else x)

    df["status_code"], df["play_prob"] = zip(
        *df["status_raw"].apply(_parse_status)
    )
    df["name_key"] = df["player_name"].apply(
        lambda x: fold_name(str(x)) if pd.notna(x) else "")
    return df


# ---------------------------------------------------------------------------
# Player ID resolution
# ---------------------------------------------------------------------------

def _build_name_key_map(db_path: str = DB_PATH) -> Dict[str, int]:
    """Return {name_key: player_id} from players table."""
    conn = get_conn(db_path)
    try:
        rows = conn.execute("SELECT player_id, name_key FROM players").fetchall()
    finally:
        conn.close()
    return {r["name_key"]: r["player_id"] for r in rows}


def resolve_player_ids(
    injury_df: pd.DataFrame,
    db_path: str = DB_PATH,
) -> pd.DataFrame:
    """Add player_id column by matching name_key against players table."""
    if injury_df.empty:
        return injury_df
    nk_map = _build_name_key_map(db_path)
    injury_df = injury_df.copy()
    injury_df["player_id"] = injury_df["name_key"].map(nk_map)
    unmatched = injury_df[injury_df["player_id"].isna()]
    if not unmatched.empty:
        log.debug("Unmatched injury players (%d): %s",
                  len(unmatched), list(unmatched["player_name"].head(5)))
    injury_df = injury_df.dropna(subset=["player_id"])
    injury_df["player_id"] = injury_df["player_id"].astype(int)
    return injury_df


# ---------------------------------------------------------------------------
# Minutes redistribution helpers
# ---------------------------------------------------------------------------

def _normalise_position(pos: Optional[str]) -> str:
    """Map raw position string to G / F / C group."""
    if not pos:
        return "F"
    p = str(pos).strip().upper()
    if p in ("PG", "SG", "G"):
        return "G"
    if p in ("C", "F-C", "C-F"):
        return "C"
    return "F"   # SF, PF, F, G-F, F-G → forward


def _get_team_rotation(
    team_id: int,
    before_date: str,
    season: str,
    db_path: str,
    n_games: int = 15,
) -> pd.DataFrame:
    """Return DataFrame of team rotation players with avg minutes."""
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT p.player_id, p.name, p.position"
            " FROM players p"
            " WHERE p.team_id = ?",
            (team_id,)
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return pd.DataFrame()

    records = []
    for r in rows:
        df = get_player_recent_games(
            r["player_id"], before_date, n_games=n_games,
            season_filter=season, min_minutes=REDISTRIB_MIN_ELIGIBLE, db_path=db_path)
        if df.empty:
            continue
        avg_min = df["min"].mean()
        records.append({
            "player_id": r["player_id"],
            "name": r["name"],
            "position": r["position"],
            "avg_min": avg_min,
        })

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values("avg_min", ascending=False)


def redistribute_minutes(
    out_player_id: int,
    out_player_avg_min: float,
    out_player_position: str,
    team_id: int,
    before_date: str,
    season: str,
    existing_overrides: Dict[int, float],
    db_path: str = DB_PATH,
) -> Dict[int, float]:
    """Position-aware redistribution of an OUT player's minutes (P13).

    Three-tier logic:
      1. Minutes pool is apportioned to G/F/C groups via _POS_FLOW.
      2. Within each group the primary backup (highest avg_min) receives
         REDISTRIB_PRIMARY_SHARE of the group pool; the residual is split
         proportionally across the rest of the group by avg_min.
      3. All bumps are scaled by REDISTRIB_EFFICIENCY (0.90) to discount
         above-optimal usage efficiency.

    Players are eligible only if avg_min >= REDISTRIB_MIN_ELIGIBLE and they
    are not the absent player.  Each recipient is capped at REDISTRIB_MAX_MIN.
    """
    rotation = _get_team_rotation(team_id, before_date, season, db_path)
    if rotation.empty:
        return existing_overrides

    eligible = rotation[
        (rotation["player_id"] != out_player_id) &
        (rotation["avg_min"] >= REDISTRIB_MIN_ELIGIBLE)
    ].copy()
    if eligible.empty:
        return existing_overrides

    eligible["norm_pos"] = eligible["position"].apply(_normalise_position)
    out_pos   = _normalise_position(out_player_position)
    pos_flow  = _POS_FLOW.get(out_pos, _DEFAULT_POS_FLOW)

    for pos_group, flow_share in pos_flow.items():
        group = eligible[eligible["norm_pos"] == pos_group].sort_values(
            "avg_min", ascending=False)
        if group.empty:
            continue

        pool = out_player_avg_min * flow_share

        # Primary backup: highest avg_min in this position group
        primary = group.iloc[0]
        primary_bump = pool * REDISTRIB_PRIMARY_SHARE * REDISTRIB_EFFICIENCY
        pid = int(primary["player_id"])
        current = existing_overrides.get(pid, primary["avg_min"])
        existing_overrides[pid] = min(current + primary_bump, REDISTRIB_MAX_MIN)
        log.debug("  [%s primary] %s: +%.1f min → %.1f",
                  pos_group, primary["name"], primary_bump, existing_overrides[pid])

        # Secondary players: proportional by avg_min
        secondary = group.iloc[1:]
        if secondary.empty:
            continue
        sec_pool = pool * (1.0 - REDISTRIB_PRIMARY_SHARE) * REDISTRIB_EFFICIENCY
        total_sec = secondary["avg_min"].sum()
        for _, row in secondary.iterrows():
            bump = sec_pool * (row["avg_min"] / total_sec)
            pid  = int(row["player_id"])
            current = existing_overrides.get(pid, row["avg_min"])
            existing_overrides[pid] = min(current + bump, REDISTRIB_MAX_MIN)
            log.debug("  [%s secondary] %s: +%.1f min → %.1f",
                      pos_group, row["name"], bump, existing_overrides[pid])

    return existing_overrides


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def get_injury_context(
    game_date: Optional[str] = None,
    season: str = "2025-26",
    db_path: str = DB_PATH,
) -> Tuple[Dict[int, str], Dict[int, float]]:
    """Fetch injury report and compute status + minutes overrides.

    Args:
        game_date: "YYYY-MM-DD" (default: today)
        season: NBA season string
        db_path: SQLite DB path

    Returns:
        (injury_statuses, injury_minutes_overrides)
        - injury_statuses:          {player_id: status_code}
        - injury_minutes_overrides: {player_id: adjusted_minutes}
    """
    date = datetime.date.fromisoformat(game_date) if game_date else datetime.date.today()
    date_str = str(date)

    # Only process players on teams that actually have a game today
    conn = get_conn(db_path)
    active_team_ids: set[int] = set()
    for row in conn.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_date=?", (date_str,)
    ).fetchall():
        active_team_ids.add(row["home_team_id"])
        active_team_ids.add(row["away_team_id"])
    conn.close()

    injury_df = fetch_injury_report(date)
    if injury_df.empty:
        log.info("No injury data -- proceeding with no adjustments")
        return {}, {}

    injury_df = resolve_player_ids(injury_df, db_path)
    if injury_df.empty:
        return {}, {}

    if not active_team_ids:
        log.warning("get_injury_context: no active games found for %s — "
                    "injury report not filtered by team (possible seed failure)", date_str)
    else:
        conn = get_conn(db_path)
        try:
            pid_to_team = {
                r["player_id"]: r["team_id"]
                for r in conn.execute("SELECT player_id, team_id FROM players").fetchall()
            }
        finally:
            conn.close()
        injury_df = injury_df[
            injury_df["player_id"].map(pid_to_team).isin(active_team_ids)
        ]
        if injury_df.empty:
            log.warning("get_injury_context: no injury report players matched active-game teams for %s", date_str)
            return {}, {}

    injury_statuses: Dict[int, str] = {}
    injury_minutes_overrides: Dict[int, float] = {}

    out_players: List[Tuple[int, int, str]] = []  # (player_id, team_id, position)

    for _, row in injury_df.iterrows():
        pid    = int(row["player_id"])
        code   = row["status_code"]
        if not code:
            continue
        injury_statuses[pid] = code

        if code in ("O",):  # confirmed out / doubtful-treated-as-out
            conn = get_conn(db_path)
            try:
                team_row = conn.execute(
                    "SELECT team_id, position FROM players WHERE player_id=?", (pid,)
                ).fetchone()
            finally:
                conn.close()
            if team_row:
                out_players.append((
                    pid,
                    int(team_row["team_id"]),
                    team_row["position"] or "",
                ))

    log.info("Injury statuses: %d players flagged (%d OUT)",
             len(injury_statuses),
             sum(1 for c in injury_statuses.values() if c == "O"))

    # Minutes redistribution for OUT players (P13 — position-aware)
    for out_pid, team_id, out_pos in out_players:
        df = get_player_recent_games(
            out_pid, date_str, n_games=15, season_filter=season, db_path=db_path)
        if df.empty:
            continue
        # M2: use EWMA (matching nba_projector) not simple mean — prevents
        # over-estimating the minutes pool for injury-volatile players.
        avg_min = float(
            df.sort_values("game_date")["min"]
            .clip(upper=44.0)
            .ewm(span=8, min_periods=1).mean().iloc[-1]
        )
        if avg_min < REDISTRIB_MIN_ELIGIBLE:
            continue   # bench players -- not worth redistributing
        log.info("Redistributing %.1f min from OUT player (id=%d, pos=%s) to team %d",
                 avg_min, out_pid, out_pos or "?", team_id)
        redistribute_minutes(
            out_player_id=out_pid,
            out_player_avg_min=avg_min,
            out_player_position=out_pos,
            team_id=team_id,
            before_date=date_str,
            season=season,
            existing_overrides=injury_minutes_overrides,
            db_path=db_path,
        )

    # M16: clamp overrides to [0, 48] (NBA); log any that were out-of-range
    _MAX_OVERRIDE = 48.0
    for pid, mins in list(injury_minutes_overrides.items()):
        clamped = max(0.0, min(_MAX_OVERRIDE, mins))
        if clamped != mins:
            log.warning("M16: minute override for player_id=%s clamped %s → %s", pid, mins, clamped)
            injury_minutes_overrides[pid] = clamped

    return injury_statuses, injury_minutes_overrides


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> None:
    import argparse, json
    parser = argparse.ArgumentParser(description="Fetch NBA injury report + compute minute overrides")
    parser.add_argument("--date",   default=str(datetime.date.today()))
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--db",     default=DB_PATH)
    parser.add_argument("--json",   action="store_true", help="Output as JSON")
    args = parser.parse_args()

    statuses, overrides = get_injury_context(
        game_date=args.date, season=args.season, db_path=args.db)

    if args.json:
        print(json.dumps({"statuses": statuses, "overrides": overrides}, indent=2))
        return

    print(f"\nInjury statuses ({len(statuses)} players):")
    for pid, code in sorted(statuses.items(), key=lambda x: x[1]):
        print(f"  player_id={pid:>8}  status={code}")

    print(f"\nMinutes overrides ({len(overrides)} players):")
    for pid, mins in sorted(overrides.items(), key=lambda x: -x[1]):
        print(f"  player_id={pid:>8}  adj_min={mins:.1f}")


if __name__ == "__main__":
    _main()
