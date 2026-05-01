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
    get_team_pace, get_player_b2b_context, get_team_def_ratio,
)
from nba_projector import (
    compute_shooting_rates, compute_per_minute_rates,
    EWMA_SPAN, LEAGUE_AVG_PACE, MATCHUP_CLIP,
)

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


def sample_games(season: str, n: int, min_min: float, db_path: Path,
                 seed: int | None = None) -> pd.DataFrame:
    """Pull n random player-game rows from the season with min >= min_min.

    If n <= 0, returns ALL qualifying rows (deterministic, no sampling).
    seed is applied at the Python level after a full pull when n > 0.
    """
    conn = get_conn(db_path)
    # Pull all qualifying rows, then sample in Python for reproducible seeding
    df = pd.read_sql_query(
        """
        SELECT pgs.player_id, pgs.team_id, p.name AS player_name,
               p.position,
               g.game_date, g.season,
               g.home_team_id, g.away_team_id,
               pgs.pts, pgs.reb, pgs.ast, pgs.fg3m, pgs.stl, pgs.blk,
               pgs.min, pgs.fga, pgs.fta
        FROM player_game_stats pgs
        JOIN games g      ON g.game_id  = pgs.game_id
        JOIN players p    ON p.player_id = pgs.player_id
        WHERE g.season = :season
          AND pgs.min >= :min_min
        """,
        conn,
        params={"season": season, "min_min": min_min},
    )
    conn.close()
    if n > 0 and n < len(df):
        df = df.sample(n=n, random_state=seed)
    return df.reset_index(drop=True)


_PTS_BLEND_ALPHA = 0.50  # must match PTS_BLEND_ALPHA in nba_projector.py


def project_pts(player_id: int, team_id: int, opp_team_id: int,
                position: str, game_date: str,
                season: str, proj_min: float, db_path: Path) -> float | None:
    """Project PTS using 50/50 blend of FGA-decomp + per-min baseline.

    Mirrors the blend logic in nba_projector.py (calibrated Apr 30 2026).
    """
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

    rates = compute_per_minute_rates(df)

    team_avg_fga = get_team_avg_fga(team_id, game_date, season, db_path=db_path)
    raw_pace     = get_team_pace(team_id, season, db_path=db_path)
    pace_factor  = raw_pace / LEAGUE_AVG_PACE  # normalised ratio ~1.0

    proj_fga = (usg_pct / 100.0) * team_avg_fga * pace_factor * (proj_min / 48.0)
    proj_3pa = fg3a_rate * proj_fga
    proj_2pa = (1.0 - fg3a_rate) * proj_fga
    proj_fta = fta_fga_ratio * proj_fga
    proj_pts_fga = proj_2pa * 2.0 * fg2_pct + proj_3pa * 3.0 * fg3_pct + proj_fta * ft_pct

    # DvP matchup factor
    pos_grp = _pos_to_group(position)
    matchup_pts = get_team_def_ratio(opp_team_id, pos_grp, "pts", season, db_path=db_path)
    matchup_pts = max(MATCHUP_CLIP[0], min(MATCHUP_CLIP[1], matchup_pts))
    proj_pts_fga *= matchup_pts

    # 50/50 blend with per-minute baseline
    baseline_pts = rates.get("pts", 0.0) * proj_min
    proj_pts = _PTS_BLEND_ALPHA * proj_pts_fga + (1.0 - _PTS_BLEND_ALPHA) * baseline_pts

    return round(proj_pts, 2)


def _pos_to_group(position: str) -> str:
    """Map raw position string to DvP position group (Guard/Forward/Center)."""
    pos = (position or "").upper().strip()
    if pos in ("PG", "SG", "G"):
        return "Guard"
    if pos in ("SF", "PF", "F"):
        return "Forward"
    if pos in ("C",):
        return "Center"
    # Multi-position (G-F, F-C, etc.) — use first token
    first = pos.split("-")[0].strip()
    return _pos_to_group(first) if first != pos else "Forward"  # safe default


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
                   db_path: Path, verbose: bool, seed: int | None = None) -> dict:

    log.info("Sampling %d player-games from %s (min>=%.0f) ...", n, season, min_min)
    sample = sample_games(season, n, min_min, db_path, seed=seed)
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
            pos    = str(row.get("position", "") or "")
            # opponent = the other team in the game; guard against NULL
            home_raw = row["home_team_id"]
            away_raw = row["away_team_id"]
            if pd.isna(home_raw) or pd.isna(away_raw):
                opp_tid = 0  # unknown — DvP will return 1.0 fallback
            else:
                home_tid = int(home_raw)
                away_tid = int(away_raw)
                opp_tid  = away_tid if tid == home_tid else home_tid

            if stat.upper() == "PTS":
                custom = project_pts(pid, tid, opp_tid, pos, gdate, szn, pmin, db_path)
            else:
                custom = project_per_min(pid, gdate, szn, pmin, stat, db_path)

            baseline = project_per_min(pid, gdate, szn, pmin, stat, db_path)

            if custom is None or baseline is None:
                skipped += 1
                continue

            blend = (custom + baseline) / 2.0  # 50/50 ensemble
            results.append({
                "player":   row["player_name"],
                "date":     gdate,
                "actual":   actual,
                "custom":   custom,
                "baseline": baseline,
                "blend":    blend,
                "min":      pmin,
                "custom_err":   custom - actual,
                "baseline_err": baseline - actual,
                "blend_err":    blend - actual,
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
    blend_mae   = float(df["blend_err"].abs().mean())
    custom_bias = float(df["custom_err"].mean())
    base_bias   = float(df["baseline_err"].mean())
    blend_bias  = float(df["blend_err"].mean())
    custom_rmse = float(np.sqrt((df["custom_err"]**2).mean()))
    base_rmse   = float(np.sqrt((df["baseline_err"]**2).mean()))
    blend_rmse  = float(np.sqrt((df["blend_err"]**2).mean()))
    delta_mae   = custom_mae - base_mae

    return {
        "n_eval":       n_eval,
        "skipped":      skipped,
        "stat":         stat.upper(),
        "season":       season,
        "custom_mae":   custom_mae,
        "baseline_mae": base_mae,
        "blend_mae":    blend_mae,
        "custom_bias":  custom_bias,
        "baseline_bias": base_bias,
        "blend_bias":   blend_bias,
        "custom_rmse":  custom_rmse,
        "baseline_rmse": base_rmse,
        "blend_rmse":   blend_rmse,
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
    parser.add_argument("--seed",      type=int, default=42,
                        help="Random seed for reproducible sampling (default: 42)")
    parser.add_argument("--verbose",   action="store_true")
    args = parser.parse_args()

    out = run_evaluation(
        season=args.season,
        n=args.n,
        stat=args.stat,
        min_min=args.min_games,
        db_path=Path(args.db),
        verbose=args.verbose,
        seed=args.seed,
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
  Blend   MAE:  {out['blend_mae']:.3f}   RMSE={out['blend_rmse']:.3f}   bias={out['blend_bias']:+.3f}

  Delta (custom vs base): {out['delta_mae']:+.3f} ({out['pct_delta']:+.1f}%)  {sign} Custom {arrow} than per-min baseline
{'='*60}
""")


if __name__ == "__main__":
    _main()
