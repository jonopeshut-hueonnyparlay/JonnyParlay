"""
calibrate_sigma.py — Normal-path sigma calibration for NBA stats.

Computes within-player CV (std/mean) from player_game_stats in projections.db.
The 'mult' for SIGMA[stat] should equal the median within-player CV.
The 'min' should equal the p10 std (so low-projection players keep a sensible floor).

Stats calibrated:
  PTS  — single-stat Normal prop + combo path component
  REB  — combo path only (single-stat REB routes through NB_STATS r=10.18)
  AST  — combo path only (single-stat AST routes through NB_STATS r=9.68)
         Currently no SIGMA["AST"] entry — falls back to {"mult": 0.40, "min": 2.0}

Stats NOT calibrated here (no game log data in projections.db):
  OUTS, HA — MLB pitcher stats — require separate MLB game log DB
  REC      — NFL receptions — not live in production

Usage:
  python engine/calibrate_sigma.py
  python engine/calibrate_sigma.py --min-games 15 --min-mean 3.0
"""

import argparse
import sqlite3
import statistics
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "projections.db"

# Current production values from run_picks.py SIGMA dict
CURRENT_SIGMA = {
    "PTS": {"mult": 0.35, "min": 4.5},
    "REB": {"mult": 0.58, "min": 2.5},
    # AST has no entry — falls back to {"mult": 0.40, "min": 2.0}
}
AST_FALLBACK = {"mult": 0.40, "min": 2.0}

# Column name in player_game_stats for each stat
STAT_COL = {
    "PTS": "pts",
    "REB": "reb",
    "AST": "ast",
}

# Only use games where the player played meaningful minutes (filters DNPs/garbage)
MIN_MINUTES = 5.0


def calibrate(conn, stat: str, min_games: int, min_mean: float) -> dict | None:
    """Compute within-player CV stats for one stat from player_game_stats."""
    col = STAT_COL[stat]
    # Pull all qualifying game rows: min >= MIN_MINUTES so DNPs don't corrupt variance
    rows = conn.execute(
        f"""
        SELECT player_id, {col}
        FROM player_game_stats
        WHERE min >= ? AND {col} IS NOT NULL
        ORDER BY player_id
        """,
        (MIN_MINUTES,),
    ).fetchall()

    if not rows:
        return None

    # Group by player
    from collections import defaultdict
    player_vals: dict[int, list[float]] = defaultdict(list)
    for pid, val in rows:
        player_vals[pid].append(float(val))

    cvs = []
    stds = []
    means_used = []
    n_players = 0

    for pid, vals in player_vals.items():
        if len(vals) < min_games:
            continue
        mean = statistics.mean(vals)
        if mean < min_mean:
            continue
        std = statistics.pstdev(vals)  # population std (same player, all games = population)
        if mean == 0:
            continue
        cv = std / mean
        cvs.append(cv)
        stds.append(std)
        means_used.append(mean)
        n_players += 1

    if not cvs:
        return None

    cvs_sorted = sorted(cvs)
    stds_sorted = sorted(stds)
    n = len(cvs_sorted)

    return {
        "n_players": n_players,
        "n_games_total": len(rows),
        "median_cv": cvs_sorted[n // 2],
        "p25_cv": cvs_sorted[n // 4],
        "p75_cv": cvs_sorted[3 * n // 4],
        "p10_std": stds_sorted[max(0, n // 10)],
        "median_std": stds_sorted[n // 2],
        "median_mean": sorted(means_used)[n // 2],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-games", type=int, default=20,
                        help="Minimum games per player to include (default: 20)")
    parser.add_argument("--min-mean", type=float, default=3.0,
                        help="Minimum mean stat value to include player (default: 3.0)")
    parser.add_argument("--db", default=None, help="Override DB path")
    args = parser.parse_args()

    db = Path(args.db) if args.db else DB_PATH
    conn = sqlite3.connect(db)

    print(f"\ncalibrate_sigma.py — NBA Normal-path sigma calibration")
    print(f"DB: {db}")
    print(f"Filters: min_games>={args.min_games}, min_mean>={args.min_mean}, min_minutes>={MIN_MINUTES}")
    print()

    for stat in ("PTS", "REB", "AST"):
        result = calibrate(conn, stat, args.min_games, args.min_mean)
        if result is None:
            print(f"{stat}: no data")
            continue

        current = CURRENT_SIGMA.get(stat, AST_FALLBACK)
        cal_mult = result["median_cv"]
        cal_min  = result["p10_std"]

        print(f"{'-'*60}")
        print(f"  {stat}")
        print(f"  {'Players':15s}: {result['n_players']} (n_games>={args.min_games}, mean>={args.min_mean})")
        print(f"  {'Total rows':15s}: {result['n_games_total']}")
        print(f"  {'Median mean':15s}: {result['median_mean']:.2f}")
        print()
        print(f"  {'CV (std/mean)':15s}: p25={result['p25_cv']:.3f}  median={result['median_cv']:.3f}  p75={result['p75_cv']:.3f}")
        print(f"  {'Abs std':15s}: p10={result['p10_std']:.2f}  median={result['median_std']:.2f}")
        print()
        print(f"  Current  SIGMA['{stat}'] = mult={current['mult']:.3f}  min={current['min']:.1f}")
        print(f"  Calibrated             = mult={cal_mult:.3f}  min={cal_min:.1f}")

        delta_mult = cal_mult - current["mult"]
        delta_min  = cal_min  - current["min"]
        flag_mult = " ** LARGE DIFF" if abs(delta_mult) > 0.05 else ""
        flag_min  = " ** LARGE DIFF" if abs(delta_min)  > 1.0  else ""
        print(f"  Delta                  = mult={delta_mult:+.3f}{flag_mult}  min={delta_min:+.1f}{flag_min}")

        if stat == "REB":
            print(f"  NOTE: REB used by combo path only -- single-stat REB uses NB_STATS (r=10.18)")
        if stat == "AST":
            print(f"  NOTE: AST has NO current SIGMA entry -- add to SIGMA for combo path (PA/RA/PRA)")
            print(f"  Fallback currently: mult={AST_FALLBACK['mult']:.3f}  min={AST_FALLBACK['min']:.1f}")
        print()

    print(f"{'-'*60}")
    print("MLB stats (OUTS, HA, K, HRR) not calibrated -- no game log data in projections.db.")
    print("Needs separate MLB stats DB (statsapi). See backlog.")
    print()
    print("To deploy: paste updated mult/min values into SIGMA dict in engine/run_picks.py.")
    print("For AST: add SIGMA['AST'] entry. Mark combo-path only in comment.")

    conn.close()


if __name__ == "__main__":
    main()
