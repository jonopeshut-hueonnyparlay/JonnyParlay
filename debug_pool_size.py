"""Quick check: how many players per team pass the new pool filter."""
import sys, datetime
sys.path.insert(0, "engine")

from projections_db import DB_PATH, get_conn
from nba_projector import CURRENT_SEASON, MIN_GAMES_FOR_TIER

game_date = str(datetime.date.today())
season = CURRENT_SEASON

conn = get_conn(DB_PATH)
conn.row_factory = __import__("sqlite3").Row

# Teams playing today
teams = conn.execute(
    "SELECT DISTINCT th.team_id, th.abbreviation, g.game_id"
    " FROM games g"
    " JOIN teams th ON th.team_id IN (g.home_team_id, g.away_team_id)"
    " WHERE g.game_date=?", (game_date,)
).fetchall()

print(f"\nPlayer pool sizes for {game_date} (season={season})\n")
print(f"{'Team':<6}  {'OLD (any season, mg=2)':>22}  {'NEW (cur season, mg=5)':>22}")
print("-" * 56)

for t in teams:
    tid = t["team_id"]
    abbr = t["abbreviation"]

    old_count = conn.execute(
        "SELECT COUNT(DISTINCT p.player_id) FROM players p"
        " WHERE p.team_id=?"
        " AND (SELECT COUNT(*) FROM player_game_stats pgs"
        "      JOIN games g ON g.game_id=pgs.game_id"
        "      WHERE pgs.player_id=p.player_id"
        "      AND g.game_date<? AND pgs.min>=5) >= 2",
        (tid, game_date)
    ).fetchone()[0]

    new_count = conn.execute(
        "SELECT COUNT(DISTINCT p.player_id) FROM players p"
        " WHERE p.team_id=?"
        " AND (SELECT COUNT(*) FROM player_game_stats pgs"
        "      JOIN games g ON g.game_id=pgs.game_id"
        "      WHERE pgs.player_id=p.player_id"
        "      AND g.game_date<? AND pgs.min>=5"
        "      AND g.season=?) >= 5",
        (tid, game_date, season)
    ).fetchone()[0]

    print(f"{abbr:<6}  {old_count:>22}  {new_count:>22}")

conn.close()
print()
print("Target: ~13-15 per team (typical playoff active roster)")
