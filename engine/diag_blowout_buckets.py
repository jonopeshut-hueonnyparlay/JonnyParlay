"""D2 diagnostic: starter minutes by |final-margin| bucket.

Fits the empirical reduction-vs-margin curve so the blowout sigmoid
(BLOWOUT_SIGMOID_K, _MID, MAX_REDUCTION in nba_projector.py) can be
re-calibrated.  Uses 2024-25 + 2025-26 Regular Season games.

Output:
  - data/diagnostics/blowout_starters.csv  (per-row: game_id, margin, player_id, starter_flag, min)
  - bucket summary table printed to stdout

Run: python engine/diag_blowout_buckets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import math

import pandas as pd

from projections_db import DB_PATH, get_conn

OUT_PATH = _HERE.parent / "data" / "diagnostics" / "blowout_starters.csv"
BUCKETS = [
    ("0-5",   0,  5),
    ("5-10",  5, 10),
    ("10-15",10, 15),
    ("15-20",15, 20),
    ("20-25",20, 25),
    ("25-30",25, 30),
    ("30-35",30, 35),
    ("35+",  35, 999),
]


def pull_data() -> pd.DataFrame:
    conn = get_conn(DB_PATH)
    # Team totals per game
    team_pts = pd.read_sql_query(
        """SELECT pgs.game_id, pgs.team_id, SUM(pgs.pts) as team_pts
           FROM player_game_stats pgs
           JOIN games g ON g.game_id=pgs.game_id
           WHERE g.season IN ('2024-25','2025-26')
             AND g.season_type='Regular Season'
           GROUP BY pgs.game_id, pgs.team_id""",
        conn)
    # Compute |margin| per game (max - min of team totals)
    margins = team_pts.groupby("game_id")["team_pts"].agg(lambda s: float(s.max() - s.min()))
    margins = margins.rename("margin").reset_index()

    # Pull starters' minutes
    starters = pd.read_sql_query(
        """SELECT pgs.game_id, pgs.player_id, pgs.team_id, pgs.min
           FROM player_game_stats pgs
           JOIN games g ON g.game_id=pgs.game_id
           WHERE g.season IN ('2024-25','2025-26')
             AND g.season_type='Regular Season'
             AND pgs.starter_flag=1
             AND pgs.min IS NOT NULL""",
        conn)
    conn.close()
    df = starters.merge(margins, on="game_id")
    return df


def fit_sigmoid(buckets: pd.DataFrame, baseline: float = 32.0) -> dict:
    """Fit factor = 1 - max_reduction / (1 + exp(-k * (margin - mid))) to bucket means.

    Returns dict with fitted params.  Uses simple grid search since the
    parameter space is low-dimensional and we want robustness over speed.
    """
    margins = buckets["midpoint"].values
    factors = (buckets["mean_min"] / baseline).values

    best = (1e9, None, None, None)
    for max_red in [v / 100.0 for v in range(8, 51, 1)]:
        for mid in [v / 2.0 for v in range(0, 51, 1)]:  # 0 to 25 step 0.5
            for k in [v / 100.0 for v in range(5, 81, 5)]:
                preds = []
                for m in margins:
                    factor = 1.0 - max_red / (1.0 + math.exp(-k * (m - mid)))
                    preds.append(factor)
                mse = sum((p - f) ** 2 for p, f in zip(preds, factors)) / len(preds)
                if mse < best[0]:
                    best = (mse, max_red, mid, k)
    return {"mse": best[0], "max_reduction": best[1], "mid": best[2], "k": best[3]}


def main() -> None:
    df = pull_data()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(df)} starter rows to {OUT_PATH}")
    print(f"Distinct games: {df['game_id'].nunique()}")
    print(f"Margin distribution: min={df['margin'].min():.1f} max={df['margin'].max():.1f} mean={df['margin'].mean():.2f}\n")

    # Bucket
    rows = []
    for label, lo, hi in BUCKETS:
        sub = df[(df["margin"] >= lo) & (df["margin"] < hi)]
        if sub.empty:
            continue
        rows.append({
            "bucket": label,
            "lo": lo, "hi": hi,
            "midpoint": float(sub["margin"].mean()),  # actual mean margin within bucket
            "n_games": sub["game_id"].nunique(),
            "n_rows":  len(sub),
            "mean_min": sub["min"].mean(),
            "median_min": sub["min"].median(),
        })
    bdf = pd.DataFrame(rows)
    print("STARTER MINUTES BY |FINAL MARGIN| BUCKET")
    print(bdf.to_string(index=False))

    # Compute implied reduction factor vs base bucket (0-5) for normalization
    base_mean = bdf.iloc[0]["mean_min"]
    print(f"\nBase bucket mean (0-5 margin): {base_mean:.2f} min")
    bdf["factor_vs_base"] = bdf["mean_min"] / base_mean
    bdf["implied_reduction"] = 1.0 - bdf["factor_vs_base"]
    print("\nImplied reduction (relative to 0-5 bucket):")
    print(bdf[["bucket", "mean_min", "factor_vs_base", "implied_reduction"]].to_string(index=False))

    # Fit sigmoid: target = factor_vs_base (so 0-5 bucket = 1.0 by construction)
    print("\nSIGMOID FIT (target = act_min / mean_min_at_0to5)")
    base = float(bdf.iloc[0]["mean_min"])
    fit = fit_sigmoid(bdf, baseline=base)
    print(f"  best params: max_reduction={fit['max_reduction']:.3f} mid={fit['mid']:.1f} k={fit['k']:.2f}  (MSE={fit['mse']:.5f})")
    print(f"  current model: max_reduction=0.200 mid=12.0 k=0.40")

    # Show fit predictions vs actuals
    print(f"\n{'Bucket':<8} {'mid':>4} {'factor_emp':>10} {'fit_factor':>11} {'diff':>6}")
    for _, r in bdf.iterrows():
        m = r["midpoint"]
        f_emp = r["factor_vs_base"]
        f_fit = 1.0 - fit["max_reduction"] / (1.0 + math.exp(-fit["k"] * (m - fit["mid"])))
        print(f"{r['bucket']:<8} {m:>4.1f} {f_emp:>10.3f} {f_fit:>11.3f} {f_fit - f_emp:>+6.3f}")


if __name__ == "__main__":
    main()
