"""nb_calibrate.py -- compute within-player NB dispersion parameter r for each stat.

Methodology: same as used for 3PM (NB_R["3PM"]=12.3 in run_picks.py).
  r = avg_mu / (avg(var/mu) - 1)

This is within-player conditional variance -- the right quantity for per-game
probability modeling (we condition on a specific player's projection).
"""
import sqlite3

DB_PATH = "data/projections.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Within-player NB dispersion calibration")
print("=" * 60)
print(f"{'Stat':<6} {'n_psn':>6} {'avg_mu':>8} {'avg(v/u)':>10} {'r':>8} {'current_r':>10} {'Poisson?':>10}")
print("-" * 60)

CURRENT = {"3PM": 12.3, "AST": None, "REB": None}

for stat, col, current_r in [
    ("3PM",  "fg3m", 12.3),
    ("AST",  "ast",  None),
    ("REB",  "reb",  None),
]:
    cur.execute(f"""
        SELECT gs.player_id, ga.season,
               AVG(CAST(gs.{col} AS FLOAT)) as mu,
               (AVG(CAST(gs.{col} AS FLOAT)*CAST(gs.{col} AS FLOAT))
                - AVG(CAST(gs.{col} AS FLOAT))*AVG(CAST(gs.{col} AS FLOAT))) as var_s,
               COUNT(*) as n_games
        FROM player_game_stats gs
        JOIN games ga ON gs.game_id = ga.game_id
        WHERE gs.min >= 5
        GROUP BY gs.player_id, ga.season
        HAVING n_games >= 10 AND mu > 0.1
    """)
    rows = cur.fetchall()

    ratios = []
    mus = []
    for pid, season, mu, var_s, n in rows:
        if var_s is None or var_s <= 0 or mu is None or mu <= 0:
            continue
        ratio = var_s / mu
        if ratio > 0.01:
            ratios.append(ratio)
            mus.append(mu)

    if not ratios:
        print(f"{stat:<6} NO DATA")
        continue

    avg_ratio = sum(ratios) / len(ratios)
    avg_mu = sum(mus) / len(mus)
    is_poisson = avg_ratio <= 1.0
    r = avg_mu / (avg_ratio - 1.0) if not is_poisson else float("inf")

    cur_str = str(current_r) if current_r else "N/A"
    r_str = f"{r:.2f}" if r != float("inf") else "inf (Poisson)"
    poisson_str = "YES" if is_poisson else "NO"
    print(f"{stat:<6} {len(ratios):>6} {avg_mu:>8.3f} {avg_ratio:>10.4f} {r_str:>8} {cur_str:>10} {poisson_str:>10}")

print()
print("Notes:")
print("  r = avg_mu / (avg(var/mu) - 1)")
print("  Larger r = less overdispersion (closer to Poisson)")
print("  Smaller r = more overdispersion (fatter tail, lower confidence)")
print("  3PM current r=12.3 was fitted from this same method on 2024-25 data")

conn.close()
