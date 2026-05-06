"""H6 backtest: would the proposed filter drop any actual 15+ min performer?

For each completed 2025-26 playoff game, simulate the filter as of that game's
date, then check whether any player who actually played >= 15 min in the game
would have been excluded from the projection pool.

Run: python engine/diag_h6_backtest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import pandas as pd

from projections_db import DB_PATH, get_conn

SEASON = "2025-26"
REC_THRESHOLD = 5.0
SEASON_THRESHOLD = 25.0


def filter_passes(player_id: int, team_id: int, before: str, conn) -> tuple[bool, float, float]:
    """Return (passes_filter, recent_avg, season_avg)."""
    games_df = pd.read_sql_query(
        """SELECT g.game_id FROM games g
           WHERE (g.home_team_id=:tid OR g.away_team_id=:tid)
             AND g.season=:season AND g.game_date < :before
             AND EXISTS (SELECT 1 FROM player_game_stats pgs WHERE pgs.game_id=g.game_id)
           ORDER BY g.game_date DESC LIMIT 3""",
        conn, params={"tid": team_id, "season": SEASON, "before": before})
    game_ids = list(games_df["game_id"])
    if not game_ids:
        return (False, 0.0, 0.0)

    placeholders = ",".join("?" for _ in game_ids)
    pgs = pd.read_sql_query(
        f"""SELECT min FROM player_game_stats
            WHERE player_id=? AND game_id IN ({placeholders})""",
        conn, params=[player_id] + game_ids)
    rec_total = float(pgs["min"].sum()) if not pgs.empty else 0.0
    rec_avg = rec_total / len(game_ids)

    season_df = pd.read_sql_query(
        """SELECT AVG(pgs.min) as avg_min FROM player_game_stats pgs
           JOIN games g ON g.game_id=pgs.game_id
           WHERE pgs.player_id=:pid AND g.season=:season
             AND g.game_date < :before AND pgs.min >= 5""",
        conn, params={"pid": player_id, "season": SEASON, "before": before})
    season_avg = float(season_df["avg_min"].iloc[0] or 0.0)

    return (rec_avg >= REC_THRESHOLD or season_avg >= SEASON_THRESHOLD,
            rec_avg, season_avg)


def main() -> None:
    conn = get_conn(DB_PATH)
    games = pd.read_sql_query(
        """SELECT game_id, game_date, home_team_id, away_team_id
           FROM games WHERE season=:season AND season_type='Playoffs'
             AND game_id NOT LIKE 'SCHED%'
           ORDER BY game_date""",
        conn, params={"season": SEASON})

    n_games = len(games)
    n_perfs = 0
    n_dropped = 0
    drops: list[dict] = []

    for _, g in games.iterrows():
        gid = g["game_id"]
        gdate = g["game_date"]
        # Pull all 15+ min performers from this game
        perfs = pd.read_sql_query(
            """SELECT pgs.player_id, pgs.team_id, pgs.min, p.name
               FROM player_game_stats pgs JOIN players p ON p.player_id=pgs.player_id
               WHERE pgs.game_id=:gid AND pgs.min >= 15""",
            conn, params={"gid": gid})
        for _, perf in perfs.iterrows():
            n_perfs += 1
            passes, rec, season = filter_passes(
                int(perf["player_id"]), int(perf["team_id"]), gdate, conn)
            if not passes:
                n_dropped += 1
                drops.append({
                    "game_date": gdate, "player": perf["name"],
                    "actual_min": round(float(perf["min"]), 1),
                    "rec_avg": round(rec, 1), "season_avg": round(season, 1),
                })

    conn.close()
    print(f"\nPlayoff games scanned: {n_games}")
    print(f"15+ min performances:  {n_perfs}")
    print(f"Filter false-drops:    {n_dropped} ({100*n_dropped/max(n_perfs,1):.1f}%)\n")
    if drops:
        df = pd.DataFrame(drops).sort_values(["game_date", "actual_min"], ascending=[True, False])
        print(df.to_string(index=False))
    else:
        print("Zero false drops.")


if __name__ == "__main__":
    main()
