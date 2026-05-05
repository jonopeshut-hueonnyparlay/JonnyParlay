"""projection_accuracy.py — Post-game projection accuracy CLI.

Uses actual stored projections (projections table) vs box-score results
(player_game_stats table) to compute rolling MAE, bias, and suggested new
scalars — without re-running the full historical backtest.

Usage:
    python engine/projection_accuracy.py [options]

Options:
    --days N        Look-back window in days (default: 30)
    --season STR    Filter to a specific season string (e.g. 2025-26)
    --role ROLE     Filter to one role tier (starter|sixth_man|rotation|spot|cold_start)
    --min-n N       Minimum sample size to report a cell (default: 10)
    --db PATH       Override DB path

Output:
    Overall + per-stat MAE/bias + NewScalar suggestions.
    Per-role breakdown.
    Per-role × per-stat table.
    Per-role minutes ratio (actual/proj).
    Rolling 7/14/30 day MAE trend.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from projections_db import DB_PATH, get_projection_vs_actual
from nba_projector import REGULAR_SEASON_STAT_SCALAR, REGULAR_SEASON_MINUTES_SCALAR

STAT_COLS = [
    ("PTS",  "pts",  "proj_pts",  "actual_pts"),
    ("REB",  "reb",  "proj_reb",  "actual_reb"),
    ("AST",  "ast",  "proj_ast",  "actual_ast"),
    ("3PM",  "fg3m", "proj_fg3m", "actual_fg3m"),
    ("BLK",  "blk",  "proj_blk",  "actual_blk"),
    ("STL",  "stl",  "proj_stl",  "actual_stl"),
]
ROLE_ORDER = ["starter", "sixth_man", "rotation", "spot", "cold_start"]


def _mae(errs: list) -> float:
    return float("nan") if not errs else sum(abs(e) for e in errs) / len(errs)

def _bias(errs: list) -> float:
    return float("nan") if not errs else sum(errs) / len(errs)

def _rmse(errs: list) -> float:
    return float("nan") if not errs else math.sqrt(sum(e**2 for e in errs) / len(errs))


def _compute_errors(df, proj_col: str, actual_col: str) -> list:
    """Return list of (proj - actual) for rows where both are non-null."""
    subset = df[[proj_col, actual_col]].dropna()
    return list(subset[proj_col] - subset[actual_col])


def run_accuracy_report(
    days: int = 30,
    season: str | None = None,
    role: str | None = None,
    min_n: int = 10,
    db_path: Path = DB_PATH,
) -> None:
    df = get_projection_vs_actual(days=days, season=season, role=role, db_path=db_path)

    if df.empty:
        print(f"\nNo projection vs actual data found for the last {days} days.")
        print("Ensure projections have been run (generate_projections.py) and games have completed.")
        return

    n_rows = len(df)
    date_range = f"{df['game_date'].min()} to {df['game_date'].max()}"
    print(f"\n{'='*70}")
    print(f"PROJECTION ACCURACY REPORT  (last {days} days, n={n_rows} player-games)")
    print(f"Date range: {date_range}")
    if season:
        print(f"Season filter: {season}")
    if role:
        print(f"Role filter: {role}")
    print(f"{'='*70}")

    # ---------------------------------------------------------------------------
    # Per-stat summary
    # ---------------------------------------------------------------------------
    all_errs: list = []
    print(f"\n{'Stat':6s}  {'MAE':>7s}  {'Bias':>8s}  {'RMSE':>7s}  {'MeanProj':>9s}"
          f"  {'CurrScalar':>10s}  {'NewScalar':>9s}  {'n':>5s}")

    for stat_name, stat_col, proj_col, actual_col in STAT_COLS:
        if proj_col not in df.columns or actual_col not in df.columns:
            continue
        errs = _compute_errors(df, proj_col, actual_col)
        if len(errs) < min_n:
            continue
        all_errs.extend(errs)
        mean_p   = df[proj_col].dropna().mean()
        bias_val = _bias(errs)
        sugg_corr = (mean_p - bias_val) / mean_p if mean_p > 0 else 1.0
        curr_sc  = REGULAR_SEASON_STAT_SCALAR.get(stat_col, 1.0)
        new_sc   = round(curr_sc * sugg_corr, 4)
        print(f"{stat_name:6s}  {_mae(errs):7.3f}  {bias_val:+8.3f}  {_rmse(errs):7.3f}"
              f"  {mean_p:9.3f}  {curr_sc:10.4f}  {new_sc:9.4f}  {len(errs):5d}")

    if all_errs:
        print(f"\nOverall  MAE={_mae(all_errs):.3f}  bias={_bias(all_errs):+.3f}  n={len(all_errs)}")
    print(f"  (NewScalar = CurrScalar × correction; paste into REGULAR_SEASON_STAT_SCALAR)")

    # ---------------------------------------------------------------------------
    # Minutes model
    # ---------------------------------------------------------------------------
    min_df = df[["role_tier", "proj_min", "actual_min"]].dropna()
    if len(min_df) >= min_n:
        print(f"\n{'='*70}")
        print("MINUTES MODEL")
        print(f"{'='*70}")
        min_errs = list(min_df["proj_min"] - min_df["actual_min"])
        mean_proj_min = min_df["proj_min"].mean()
        mean_act_min  = min_df["actual_min"].mean()
        ratio = mean_act_min / mean_proj_min if mean_proj_min > 0 else 1.0
        print(f"  Overall:  proj={mean_proj_min:.2f}  actual={mean_act_min:.2f}  "
              f"ratio={ratio:.4f}  bias={_bias(min_errs):+.3f}  n={len(min_errs)}")

        print(f"\n  {'Role':15s}  {'n':>5s}  {'ProjMin':>8s}  {'ActMin':>8s}  {'Ratio':>7s}"
              f"  {'CurrScalar':>10s}  {'NewScalar':>9s}  {'Bias':>7s}")
        print(f"  (NewScalar = CurrScalar × Ratio; paste into REGULAR_SEASON_MINUTES_SCALAR)")
        roles_in_data = min_df["role_tier"].unique()
        ordered = [r for r in ROLE_ORDER if r in roles_in_data]
        ordered += [r for r in sorted(roles_in_data) if r not in ROLE_ORDER]
        for r in ordered:
            sub = min_df[min_df["role_tier"] == r]
            if len(sub) < min_n:
                continue
            mp = sub["proj_min"].mean()
            ma = sub["actual_min"].mean()
            ro = ma / mp if mp > 0 else 1.0
            rb = ma - mp
            cs = REGULAR_SEASON_MINUTES_SCALAR.get(r, 1.0)
            ns = round(cs * ro, 4)
            print(f"  {r:15s}  {len(sub):5d}  {mp:8.2f}  {ma:8.2f}  {ro:7.4f}"
                  f"  {cs:10.4f}  {ns:9.4f}  {rb:+7.3f}")

    # ---------------------------------------------------------------------------
    # Per-role breakdown
    # ---------------------------------------------------------------------------
    if "role_tier" in df.columns:
        print(f"\n{'='*70}")
        print("PER-ROLE BREAKDOWN (all stats combined)")
        print(f"{'='*70}")
        print(f"  {'Role':15s}  {'MAE':>7s}  {'Bias':>7s}  {'RMSE':>7s}  {'n':>5s}")
        roles_in_data = df["role_tier"].dropna().unique()
        ordered = [r for r in ROLE_ORDER if r in roles_in_data]
        ordered += [r for r in sorted(roles_in_data) if r not in ROLE_ORDER]
        role_stat_data: dict = {}
        for r in ordered:
            sub = df[df["role_tier"] == r]
            errs = []
            for _, _, pc, ac in STAT_COLS:
                if pc in sub.columns and ac in sub.columns:
                    errs.extend(_compute_errors(sub, pc, ac))
            if len(errs) < min_n:
                continue
            role_stat_data[r] = sub
            print(f"  {r:15s}  {_mae(errs):7.3f}  {_bias(errs):+7.3f}  {_rmse(errs):7.3f}  {len(errs):5d}")

        # Per-role × per-stat
        print(f"\n  Per-role × per-stat (Bias / MeanProj / SuggCorr):")
        header = f"  {'Role':15s}" + "".join(f"  {s:>5s}(bias/sugg)" for s, *_ in STAT_COLS)
        print(header)
        for r in ordered:
            if r not in role_stat_data:
                continue
            sub = role_stat_data[r]
            row = f"  {r:15s}"
            for stat_name, _, pc, ac in STAT_COLS:
                if pc not in sub.columns or ac not in sub.columns:
                    row += "           n/a"
                    continue
                errs = _compute_errors(sub, pc, ac)
                if len(errs) < min_n:
                    row += "           n/a"
                    continue
                mean_p = sub[pc].dropna().mean()
                bias_v = _bias(errs)
                sugg   = (mean_p - bias_v) / mean_p if mean_p > 0 else 1.0
                row += f"  {bias_v:+5.2f}/{sugg:.3f}"
            print(row)

    # ---------------------------------------------------------------------------
    # Rolling trend (7/14/30 day MAE for PTS)
    # ---------------------------------------------------------------------------
    if "game_date" in df.columns and "proj_pts" in df.columns and "actual_pts" in df.columns:
        print(f"\n{'='*70}")
        print("ROLLING PTS MAE TREND")
        print(f"{'='*70}")
        import datetime as _dt
        today = _dt.date.today().isoformat()
        for window in [7, 14, 30]:
            cutoff = (_dt.date.today() - _dt.timedelta(days=window)).isoformat()
            sub = df[df["game_date"] >= cutoff]
            errs = _compute_errors(sub, "proj_pts", "actual_pts")
            if len(errs) < min_n:
                print(f"  Last {window:2d} days: n={len(errs)} (< {min_n}, skipped)")
            else:
                print(f"  Last {window:2d} days: MAE={_mae(errs):.3f}  bias={_bias(errs):+.3f}  n={len(errs)}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post-game projection accuracy report")
    parser.add_argument("--days",   type=int, default=30, help="Look-back window in days")
    parser.add_argument("--season", default=None,         help="Filter to season (e.g. 2025-26)")
    parser.add_argument("--role",   default=None,         help="Filter to role tier")
    parser.add_argument("--min-n",  type=int, default=10, help="Min sample size to report a cell")
    parser.add_argument("--db",     default=None,         help="Override DB path")
    args = parser.parse_args()

    run_accuracy_report(
        days=args.days,
        season=args.season,
        role=args.role,
        min_n=args.min_n,
        db_path=Path(args.db) if args.db else DB_PATH,
    )
