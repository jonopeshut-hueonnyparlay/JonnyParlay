"""
Debug script: print per-player projection breakdown for today's run.
Run from repo root: python debug_projections.py [--date 2026-05-04]
"""
import sys, argparse, datetime
sys.path.insert(0, "engine")

from projections_db import (
    DB_PATH, get_player_recent_games, get_player_season_game_count,
    get_conn
)
from nba_projector import CURRENT_SEASON, MIN_GAMES_FOR_TIER, classify_role

parser = argparse.ArgumentParser()
parser.add_argument("--date", default=str(datetime.date.today()))
parser.add_argument("--season", default=CURRENT_SEASON)
parser.add_argument("--players", nargs="+",
                    default=["Embiid", "Brunson", "Edwards", "Wembanyama",
                             "Maxey", "Conley", "McBride"])
args = parser.parse_args()

conn = get_conn(DB_PATH)
conn.row_factory = __import__("sqlite3").Row

print(f"\n=== Projection Debug for {args.date} (season={args.season}) ===\n")

# --- 1. Show what games are in the DB for today ---
games = conn.execute(
    "SELECT g.game_id, g.season_type, th.abbreviation AS home, ta.abbreviation AS away"
    " FROM games g"
    " JOIN teams th ON th.team_id=g.home_team_id"
    " JOIN teams ta ON ta.team_id=g.away_team_id"
    " WHERE g.game_date=?", (args.date,)
).fetchall()
print(f"Games in DB for {args.date}:")
for g in games:
    print(f"  {g['home']} vs {g['away']}  game_id={g['game_id']}  season_type={g['season_type']}")
print()

# --- 2. Per-player breakdown ---
for name_fragment in args.players:
    rows = conn.execute(
        "SELECT player_id, name, position, team_id FROM players"
        " WHERE name LIKE ?", (f"%{name_fragment}%",)
    ).fetchall()
    if not rows:
        print(f"[{name_fragment}] NOT FOUND IN players TABLE\n")
        continue

    for r in rows:
        pid      = r["player_id"]
        name     = r["name"]
        team_id  = r["team_id"]
        position = r["position"]

        games_on_team = get_player_season_game_count(pid, args.season, team_id, DB_PATH)
        df = get_player_recent_games(pid, args.date, n_games=30,
                                      season_filter=args.season, db_path=DB_PATH)

        is_cold_start = games_on_team < MIN_GAMES_FOR_TIER
        role = "cold_start" if is_cold_start else classify_role(df)
        avg_min = df["min"].head(10).mean() if not df.empty else 0.0

        print(f"[{name}] pos={position} team_id={team_id}")
        print(f"  games_on_team (2025-26): {games_on_team}  cold_start={is_cold_start}")
        print(f"  recent_games fetched: {len(df)}  avg_min(last10)={avg_min:.1f}")
        print(f"  classified_role: {role}")

        if not df.empty:
            print(f"  Last 5 game dates + minutes:")
            for _, row in df.head(5).iterrows():
                print(f"    {row['game_date']}  min={row['min']:.1f}  pts={row['pts']:.1f}  "
                      f"ast={row['ast']:.1f}  start={int(row['starter_flag'])}")
        else:
            print(f"  ** NO GAME DATA found for season={args.season} before {args.date}")

        # Also check ALL-time game count (ignoring season filter)
        all_time = conn.execute(
            "SELECT COUNT(*) FROM player_game_stats pgs"
            " JOIN games g ON g.game_id=pgs.game_id"
            " WHERE pgs.player_id=? AND pgs.min>=5", (pid,)
        ).fetchone()[0]
        seasons_in_db = conn.execute(
            "SELECT DISTINCT g.season FROM player_game_stats pgs"
            " JOIN games g ON g.game_id=pgs.game_id"
            " WHERE pgs.player_id=? AND pgs.min>=5"
            " ORDER BY g.season", (pid,)
        ).fetchall()
        print(f"  All-time games in DB: {all_time}  Seasons: {[s[0] for s in seasons_in_db]}")
        print()

conn.close()
