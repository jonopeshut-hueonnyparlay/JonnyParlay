"""evaluate_projector.py -- Direct MAE evaluation against DB history.

Samples player-game pairs from regular season, runs projections using only
data prior to that game, compares to actuals. No pick_log required.

Usage:
    python engine/evaluate_projector.py [--season 2024-25] [--n 300] [--stat PTS]
                                        [--min-games 5] [--verbose]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from projections_db import (
    DB_PATH, get_conn, get_player_recent_games, get_team_avg_fga,
    get_team_pace, get_player_b2b_context,
)
from nba_projector import compute_shooting_rates, compute_per_minute_rates, EWMA_SPAN, LEAGUE_AVG_PACE

log = logging.getLogger("evaluate")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# stat column mapping
# ---------------------------------------------------------------------------

STAT_COL = {
    "PTS": "pts", "REB": "reb", "AST": "ast",
    "3PM": "fg3m", "STL": "stl", "BLK": "blk",
}


def sample_games(season: str, n: int, min_min: float, db_path: Path) -> pd.DataFrame:
    """Pull n random player-game rows from the season with min >= min_min."""
    conn = get_conn(db_path)
    df = pd.read_sql_query(
        """
        SELECT pgs.player_id, pgs.team_id, p.name AS player_name,
               g.game_date, g.season,
               pgs.pts, pgs.reb, pgs.ast, pgs.fg3m, pgs.stl, pgs.blk,
               pgs.min, pgs.fga, pgs.fta
        FROM player_game_stats pgs
        JOIN games g      ON g.game_id  = pgs.game_id
        JOIN players p    ON p.player_id = pgs.player_id
        WHERE g.season = :season
          AND pgs.min >= :min_min
        ORDER BY RANDOM()
        LIMIT :n
        """,
        conn,
        params={"season": season, "min_min": min_min, "n": n},
    )
    conn.close()
    return df


def project_pts(player_id: int, team_id: int, game_date: str,
                season: str, proj_min: float, db_path: Path) -> float | None:
    """Project PTS for a player using only data prior to game_date."""
    df = get_player_recent_games(
        player_id, game_date, n_games=20,
        db_path=db_path,
    )
    if len(df) < 3:
        return None

    shoot = compute_shooting_rates(df)
    usg_pct       = shoot["usg_pct"]
    fg2_pct       = shoot["fg2_pct"]
    fg3_pct       = shoot["fg3_pct"]
    fg3a_rate     = shoot["fg3a_rate"]
    fta_fga_ratio = shoot["fta_fga_ratio"]
    ft_pct        = shoot["ft_pct"]

    team_avg_fga = get_team_avg_fga(team_id, game_date, season, db_path=db_path)
    raw_pace     = get_team_pace(team_id, season, db_path=db_path)
    pace_factor  = raw_pace / LEAGUE_AVG_PACE  # normalised ratio ~1.0

    proj_fga = (usg_pct / 100.0) * team_avg_fga * pace_factor * (proj_min / 48.0)
    proj_3pa = fg3a_rate * proj_fga
    proj_2pa = (1.0 - fg3a_rate) * proj_fga
    proj_fta = fta_fga_ratio * proj_fga
    proj_pts = proj_2pa * 2.0 * fg2_pct + proj_3pa * 3.0 * fg3_pct + proj_fta * ft_pct
    return round(proj_pts, 2)


def project_per_min(player_id: int, game_date: str, season: str,
                    proj_min: float, stat: str, db_path: Path) -> float | None:
    """Baseline: EWMA per-minute rate × projected minutes."""
    df = get_player_recent_games(
        player_id, game_date, n_games=20,
        db_path=db_path,
    )
    if len(df) < 3:
        return None
    col = STAT_COL.get(stat.upper())
    if col not in df.columns:
        return None
    rates = compute_per_minute_rates(df)
    # compute_per_minute_rates keys are stat names ("pts", "reb"), not "pts_per_min"
    if col not in rates:
        return None
    return round(rates[col] * proj_min, 2)


# ---------------------------------------------------------------------------
# main evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(season: str, n: int, stat: str, min_min: float,
                   db_path: Path, verbose: bool) -> dict:

    log.info("Sampling %d player-games from %s (min>=%.0f) ...", n, season, min_min)
    sample = sample_games(season, n, min_min, db_path)
    log.info("Got %d rows", len(sample))

    col = STAT_COL.get(stat.upper(), "pts")
    results = []
    skipped = 0

    for i, row in sample.iterrows():
        try:
            actual = float(row[col])
            pid    = int(row["player_id"])
            tid    = int(row["team_id"])
            gdate  = row["game_date"]
            szn    = row["season"]
            pmin   = float(row["min"])

            if stat.upper() == "PTS":
                custom = project_pts(pid, tid, gdate, szn, pmin, db_path)
            else:
                custom = project_per_min(pid, gdate, szn, pmin, stat, db_path)

            baseline = project_per_min(pid, gdate, szn, pmin, stat, db_path)

            if custom is None or baseline is None:
                skipped += 1
                continue

            results.append({
                "player":   row["player_name"],
                "date":     gdate,
                "actual":   actual,
                "custom":   custom,
                "baseline": baseline,
                "min":      pmin,
                "custom_err":   custom - actual,
                "baseline_err": baseline - actual,
            })

            if verbose and (i % 20 == 0):
                log.info("  %s  %s  actual=%.1f  custom=%.1f  base=%.1f",
                         row["player_name"], gdate, actual, custom, baseline)
        except Exception as exc:
            log.warning("Row %d error: %s", i, exc)
            skipped += 1
            continue

    if not results:
        log.error("No results — check DB has data for season %s", season)
        return {}

    df = pd.DataFrame(results)
    n_eval = len(df)

    custom_mae  = float(df["custom_err"].abs().mean())
    base_mae    = float(df["baseline_err"].abs().mean())
    custom_bias = float(df["custom_err"].mean())
    base_bias   = float(df["baseline_err"].mean())
    custom_rmse = float(np.sqrt((df["custom_err"]**2).mean()))
    base_rmse   = float(np.sqrt((df["baseline_err"]**2).mean()))
    delta_mae   = custom_mae - base_mae

    return {
        "n_eval":       n_eval,
        "skipped":      skipped,
        "stat":         stat.upper(),
        "season":       season,
        "custom_mae":   custom_mae,
        "baseline_mae": base_mae,
        "custom_bias":  custom_bias,
        "baseline_bias": base_bias,
        "custom_rmse":  custom_rmse,
        "baseline_rmse": base_rmse,
        "delta_mae":    delta_mae,
        "pct_delta":    delta_mae / base_mae * 100 if base_mae > 0 else 0,
    }


def _main():
    parser = argparse.ArgumentParser(description="Direct DB evaluation of projection engine")
    parser.add_argument("--season",    default="2025-26")
    parser.add_argument("--n",         type=int,   default=300)
    parser.add_argument("--stat",      default="PTS")
    parser.add_argument("--min-games", type=float, default=20.0,
                        help="Minimum minutes filter for sampled games")
    parser.add_argument("--db",        default=DB_PATH)
    parser.add_argument("--verbose",   action="store_true")
    args = parser.parse_args()

    out = run_evaluation(
        season=args.season,
        n=args.n,
        stat=args.stat,
        min_min=args.min_games,
        db_path=Path(args.db),
        verbose=args.verbose,
    )

    if not out:
        sys.exit(1)

    sign  = "✓" if out["delta_mae"] < 0 else "✗"
    arrow = "BETTER" if out["delta_mae"] < 0 else "WORSE"

    print(f"""
{'='*60}
Evaluation: {out['stat']} | {out['season']} | n={out['n_eval']} (skipped {out['skipped']})
{'='*60}
  Custom  MAE:  {out['custom_mae']:.3f}   RMSE={out['custom_rmse']:.3f}   bias={out['custom_bias']:+.3f}
  Baseline MAE: {out['baseline_mae']:.3f}   RMSE={out['baseline_rmse']:.3f}   bias={out['baseline_bias']:+.3f}

  Delta: {out['delta_mae']:+.3f} ({out['pct_delta']:+.1f}%)  {sign} Custom {arrow} than per-min baseline
{'='*60}
""")


if __name__ == "__main__":
    _main()
