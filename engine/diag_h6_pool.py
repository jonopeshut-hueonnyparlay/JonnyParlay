"""H6 diagnostic: dump candidate playoff pools and last-3-team-games appearance.

Identifies which players pass max_days_inactive=14 but have a DNP-heavy recent
pattern that suggests they aren't really in the active rotation.

Run: python engine/diag_h6_pool.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import pandas as pd

from projections_db import DB_PATH, get_all_active_players, get_conn

BEFORE_DATE = "2026-05-06"
SEASON = "2025-26"
TEAMS = {
    "NYK": 1610612752, "PHI": 1610612755,
    "SAS": 1610612759, "MIN": 1610612750,
    "DET": 1610612765, "CLE": 1610612739,
    "OKC": 1610612760, "LAL": 1610612747,
}


def last_n_team_games(team_id: int, before: str, n: int = 3) -> list[tuple[str, str]]:
    conn = get_conn(DB_PATH)
    try:
        df = pd.read_sql_query(
            """SELECT game_id, game_date FROM games
               WHERE (home_team_id=:tid OR away_team_id=:tid)
                 AND season=:season AND game_date < :before
               ORDER BY game_date DESC LIMIT :n""",
            conn, params={"tid": team_id, "season": SEASON,
                          "before": before, "n": n})
    finally:
        conn.close()
    return list(zip(df["game_id"], df["game_date"]))


def player_min_in_games(player_id: int, game_ids: list[str]) -> dict[str, float | None]:
    if not game_ids:
        return {}
    conn = get_conn(DB_PATH)
    try:
        placeholders = ",".join("?" for _ in game_ids)
        df = pd.read_sql_query(
            f"""SELECT game_id, min FROM player_game_stats
                WHERE player_id=? AND game_id IN ({placeholders})""",
            conn, params=[player_id] + game_ids)
    finally:
        conn.close()
    by_game = dict(zip(df["game_id"], df["min"]))
    return {gid: by_game.get(gid) for gid in game_ids}


def player_season_avg_min(player_id: int, season: str, before: str) -> float:
    """Season avg min counting only games where player has a row (DNPs excluded)."""
    conn = get_conn(DB_PATH)
    try:
        df = pd.read_sql_query(
            """SELECT AVG(pgs.min) as avg_min, COUNT(*) as n
               FROM player_game_stats pgs
               JOIN games g ON g.game_id=pgs.game_id
               WHERE pgs.player_id=:pid AND g.season=:season
                 AND g.game_date < :before AND pgs.min >= 5""",
            conn, params={"pid": player_id, "season": season, "before": before})
    finally:
        conn.close()
    avg = df["avg_min"].iloc[0]
    return float(avg) if avg is not None else 0.0


def dump_team(abbrev: str, team_id: int) -> None:
    pool = get_all_active_players(
        before_date=BEFORE_DATE, min_recent_games=5,
        season=SEASON, max_days_inactive=14)
    pool = pool[pool["team_id"] == team_id].reset_index(drop=True)

    games = last_n_team_games(team_id, BEFORE_DATE, n=3)
    game_ids = [gid for gid, _ in games]
    game_dates = [gdt for _, gdt in games]

    print(f"\n=== {abbrev} (team_id={team_id}) — pool size {len(pool)} ===")
    print(f"  last 3 team games: {', '.join(game_dates)}")

    rows = []
    for _, p in pool.iterrows():
        mins = player_min_in_games(int(p["player_id"]), game_ids)
        m_vals = [mins.get(gid) for gid in game_ids]
        # Drop the latest entry if it's None (likely SCHED row, stats not pulled yet).
        if m_vals and m_vals[0] is None:
            m_vals = m_vals[1:]
        m_zeros = [0.0 if m is None else float(m) for m in m_vals]
        played_count = sum(1 for m in m_vals if m is not None and m > 0)
        avg_with_dnp_zero = sum(m_zeros) / max(len(m_zeros), 1) if m_zeros else 0.0
        season_avg = player_season_avg_min(int(p["player_id"]), SEASON, BEFORE_DATE)
        rows.append({
            "player": p["name"],
            "pos": p["position"] or "",
            "recent": "/".join(_fmt(m) for m in m_vals),
            "played_n": played_count,
            "rec_avg(DNP=0)": round(avg_with_dnp_zero, 1),
            "season_avg": round(season_avg, 1),
        })
    df = pd.DataFrame(rows).sort_values("rec_avg(DNP=0)", ascending=False)
    print(df.to_string(index=False))


def _fmt(m: float | None) -> str:
    return "DNP" if m is None else f"{m:.0f}"


def main() -> None:
    for abbrev, tid in TEAMS.items():
        dump_team(abbrev, tid)


if __name__ == "__main__":
    main()
