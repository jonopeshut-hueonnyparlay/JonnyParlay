"""nb_calibrate.py -- compute within-player NB dispersion parameter r for each stat.

Methodology:
  r = avg_mu / (avg(var/mu) - 1)

This is within-player conditional variance -- the right quantity for per-game
probability modeling (we condition on a specific player's projection).

Stats covered:
  3PM, AST, REB  -- calibrated from projections.db (NBA game logs, 3 seasons)

Stats NOT covered here (no game log data in projections.db):
  K   -- pitcher strikeouts. Current r=5.0 is PROVISIONAL (undocumented estimate;
         bimodal distribution: early hook vs deep start). To calibrate properly:
         need MLB pitcher game logs with K per game. Query would be:
           SELECT player_id, AVG(k), VAR(k) FROM mlb_game_stats GROUP BY player_id HAVING COUNT(*)>=20
         Requires separate MLB stats DB (statsapi). See backlog.
  HRR -- hits+runs+RBI. Current r=1.5 calibrated via single-point moment-matching
         from shadow log: NB(r=1.5, mu=2.0) gives P(X>=2)=47.8%, matching empirical
         48% WR (n=1810). Method differs from the var/mu approach used here.
         Proper refit when re-enabled: within-player var/mu from MLB batter game logs,
         same query pattern as above. Zero-inflation (~37% of games) may warrant
         zero-inflated NB rather than standard NB.
"""
import sqlite3

DB_PATH = "data/projections.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Within-player NB dispersion calibration")
print("=" * 60)
print(f"{'Stat':<6} {'n_psn':>6} {'avg_mu':>8} {'avg(v/u)':>10} {'r':>8} {'current_r':>10} {'Poisson?':>10}")
print("-" * 60)

CURRENT = {"3PM": 9.15, "AST": 9.68, "REB": 10.18}

for stat, col, current_r in [
    ("3PM",  "fg3m", 9.15),
    ("AST",  "ast",  9.68),
    ("REB",  "reb",  10.18),
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
print("  Run after any DB update to check if r values need refreshing")

conn.close()
