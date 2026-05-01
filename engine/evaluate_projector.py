"""evaluate_projector.py -- Direct MAE evaluation against DB history.

Samples player-game pairs from regular season, runs projections using only
data prior to that game, compares to actuals. No pick_log required.

Usage:
    python engine/evaluate_projector.py [--season 2024-25] [--n 300] [--stat PTS]
                                        [--min-games 5] [--verbose] [--seed 42]
    python engine/evaluate_projector.py --grid-search-alpha  # PTS alpha optimisation
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
    get_team_shooting_stats,
)
from nba_projector import (
    compute_shooting_rates, compute_per_minute_rates, compute_reb_rates,
    EWMA_SPAN, LEAGUE_AVG_PACE, MATCHUP_CLIP,
    PTS_BLEND_ALPHA, BLEND_BIAS_CORRECTION,
    _REB_POS_OREB_PRIOR, _REB_POS_DREB_PRIOR, REB_ALPHA,
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


# Minimum minutes for a game to be included in per-minute rate training history.
# Must match the eval sample floor (min_games default=20) so training and
# evaluation draw from the same performance distribution — eliminates selection
# bias from limited-role games (foul trouble, blowout garbage time) that
# systematically suppress per-minute rates relative to full-game performances.
RATE_MIN_MIN = 20.0


def _compute_pts_components(player_id: int, team_id: int, opp_team_id: int,
                             position: str, game_date: str,
                             season: str, proj_min: float,
                             db_path: Path) -> dict | None:
    """Compute FGA-decomp PTS and per-min baseline for a player-game.

    Returns dict with keys: fga_pts, baseline_pts, or None if insufficient data.
    Pace: average of team + opponent pace (matches nba_projector.py).
    Rate filter: training history filtered to min>=RATE_MIN_MIN to match
    projector's df_clean filter and eliminate garbage-time rate bias.
    """
    df_raw = get_player_recent_games(
        player_id, game_date, n_games=20,
        db_path=db_path,
    )
    # Apply same min filter as projector df_clean — eliminates garbage-time bias
    df = df_raw[df_raw["min"] >= RATE_MIN_MIN].copy()
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

    # Average team + opponent pace — matches nba_projector.py.
    team_pace = get_team_pace(team_id,     season, db_path=db_path)
    opp_pace  = get_team_pace(opp_team_id, season, db_path=db_path)
    game_pace = (team_pace + opp_pace) / 2.0
    pace_factor = game_pace / LEAGUE_AVG_PACE

    proj_fga = (usg_pct / 100.0) * team_avg_fga * pace_factor * (proj_min / 48.0)
    proj_3pa = fg3a_rate * proj_fga
    proj_2pa = (1.0 - fg3a_rate) * proj_fga
    proj_fta = fta_fga_ratio * proj_fga

    # DvP matchup factor (shared for PTS and 3PM)
    pos_grp = _pos_to_group(position)
    matchup_pts = get_team_def_ratio(opp_team_id, pos_grp, "pts", season, db_path=db_path)
    matchup_pts = max(MATCHUP_CLIP[0], min(MATCHUP_CLIP[1], matchup_pts))

    fga_pts = (proj_2pa * 2.0 * fg2_pct + proj_3pa * 3.0 * fg3_pct + proj_fta * ft_pct) * matchup_pts

    # 3PM extracted from the same FGA path (Sec. 4a, Brief 3)
    fga_3pm = proj_3pa * fg3_pct * matchup_pts

    return {
        "fga_pts":      fga_pts,
        "baseline_pts": rates.get("pts",  0.0) * proj_min,
        "fga_3pm":      fga_3pm,
        "baseline_3pm": rates.get("fg3m", 0.0) * proj_min,
    }


def project_3pm(player_id: int, team_id: int, opp_team_id: int,
                position: str, game_date: str,
                season: str, proj_min: float, db_path: Path,
                alpha: float = 0.50) -> float | None:
    """Project 3PM using alpha-weighted blend of FGA-decomp + per-min baseline.

    FGA path: proj_3pa * fg3_pct * matchup_pts (extracted from PTS decomposition).
    alpha=0.50 starting point — run --grid-search-alpha with stat=3PM to optimise.
    """
    comps = _compute_pts_components(player_id, team_id, opp_team_id,
                                    position, game_date, season, proj_min, db_path)
    if comps is None:
        return None
    blended = alpha * comps["fga_3pm"] + (1.0 - alpha) * comps["baseline_3pm"]
    return round(max(0.0, blended), 2)


def project_pts(player_id: int, team_id: int, opp_team_id: int,
                position: str, game_date: str,
                season: str, proj_min: float, db_path: Path,
                alpha: float | None = None) -> float | None:
    """Project PTS using alpha-weighted blend of FGA-decomp + per-min baseline.

    alpha: weight on FGA-decomp path (0.0 = pure per-min, 1.0 = pure FGA).
           Defaults to PTS_BLEND_ALPHA (calibrated 2026-05-01: 0.30).
    BLEND_BIAS_CORRECTION (+0.386) applied after blending.
    Re-calibrate annually: --grid-search-alpha --season X-XX --n 2000 --seed 42
    """
    if alpha is None:
        alpha = PTS_BLEND_ALPHA
    comps = _compute_pts_components(player_id, team_id, opp_team_id,
                                    position, game_date, season, proj_min, db_path)
    if comps is None:
        return None
    blended = alpha * comps["fga_pts"] + (1.0 - alpha) * comps["baseline_pts"]
    return round(blended + BLEND_BIAS_CORRECTION, 2)


def _pos_to_group(position: str) -> str:
    """Map raw position string to position group key.

    Returns 'G', 'F', or 'C' — matches team_def_splits.position_group and
    the _REB_POS_*_PRIOR dict keys in nba_projector.py.
    Mirrors nba_projector._pos_group exactly so DvP lookups hit the right rows.
    """
    p = (position or "").upper().strip()
    if p.startswith("G"):
        return "G"
    if p.startswith("C"):
        return "C"
    return "F"


def project_per_min(player_id: int, game_date: str, season: str,
                    proj_min: float, stat: str, db_path: Path) -> float | None:
    """Baseline: EWMA per-minute rate x projected minutes.

    Training history filtered to min>=RATE_MIN_MIN to match projector df_clean.
    """
    df_raw = get_player_recent_games(
        player_id, game_date, n_games=20,
        db_path=db_path,
    )
    df = df_raw[df_raw["min"] >= RATE_MIN_MIN].copy()
    if len(df) < 3:
        return None
    col = STAT_COL.get(stat.upper())
    if col not in df.columns:
        return None
    rates = compute_per_minute_rates(df)
    if col not in rates:
        return None
    return round(rates[col] * proj_min, 2)


def project_reb(player_id: int, team_id: int, opp_team_id: int,
                position: str, game_date: str,
                season: str, proj_min: float, db_path: Path) -> float | None:
    """Project REB via OREB/DREB decomposition (Brief P3, Sec. 2).

    OREB: player rate per own-team miss (avail_oreb = team_FGA*(1-team_FG%)).
    DREB: player rate per opp-team miss (avail_dreb = opp_FGA*(1-opp_FG%)).
    Both rates Bayesian-shrunk to positional priors, then blended 45/55 with baseline.
    """
    df_raw = get_player_recent_games(player_id, game_date, n_games=20, db_path=db_path)
    df = df_raw[df_raw["min"] >= RATE_MIN_MIN].copy()
    if len(df) < 3:
        return None
    if "oreb" not in df.columns or "dreb" not in df.columns:
        return None

    team_shoot = get_team_shooting_stats(team_id,     season, db_path)
    opp_shoot  = get_team_shooting_stats(opp_team_id, season, db_path)
    avail_oreb = team_shoot["fga_per_game"] * (1.0 - team_shoot["fg_pct"])
    avail_dreb = opp_shoot["fga_per_game"]  * (1.0 - opp_shoot["fg_pct"])

    pos_group = _pos_to_group(position)
    oreb_rate, dreb_rate = compute_reb_rates(df, avail_oreb, avail_dreb, pos_group)

    proj_oreb = oreb_rate * avail_oreb * (proj_min / 48.0)
    proj_dreb = dreb_rate * avail_dreb * (proj_min / 48.0)

    matchup_reb = get_team_def_ratio(opp_team_id, pos_group, "reb", season, db_path=db_path)
    matchup_reb = max(MATCHUP_CLIP[0], min(MATCHUP_CLIP[1], matchup_reb))

    proj_reb_custom = (proj_oreb + proj_dreb) * matchup_reb

    rates = compute_per_minute_rates(df)
    baseline_reb = rates.get("reb", 0.0) * proj_min

    blended = REB_ALPHA * proj_reb_custom + (1.0 - REB_ALPHA) * baseline_reb
    return round(max(0.0, blended), 2)


# ---------------------------------------------------------------------------
# main evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(season: str, n: int, stat: str, min_min: float,
                   db_path: Path, verbose: bool, seed: int | None = None,
                   alpha: float | None = None) -> dict:

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
                custom = project_pts(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path, alpha=alpha)
            elif stat.upper() == "3PM":
                custom = project_3pm(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path)
            elif stat.upper() == "REB":
                custom = project_reb(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path)
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


def run_alpha_grid_search(season: str, n: int, min_min: float,
                          db_path: Path, seed: int | None = None) -> None:
    """Grid-search PTS_BLEND_ALPHA over [0.25, 0.70] to find MAE-optimal weight.

    Runs on the same sample (seed-fixed) so results are directly comparable.
    Bias correction is NOT applied during grid search so alpha absorbs it;
    re-fit BLEND_BIAS_CORRECTION against residuals AFTER locking alpha.
    """
    log.info("Alpha grid search: sampling %d games from %s ...", n, season)
    sample = sample_games(season, n, min_min, db_path, seed=seed)
    log.info("Got %d rows", len(sample))

    # Pre-compute FGA-decomp components and baseline for every row
    comps_cache = []
    actuals = []
    for _, row in sample.iterrows():
        try:
            pid  = int(row["player_id"])
            tid  = int(row["team_id"])
            gdate = row["game_date"]
            szn   = row["season"]
            pmin  = float(row["min"])
            pos   = str(row.get("position", "") or "")
            home_raw = row["home_team_id"]
            away_raw = row["away_team_id"]
            if pd.isna(home_raw) or pd.isna(away_raw):
                opp_tid = 0
            else:
                home_tid = int(home_raw)
                away_tid = int(away_raw)
                opp_tid  = away_tid if tid == home_tid else home_tid

            comps = _compute_pts_components(pid, tid, opp_tid, pos, gdate, szn, pmin, db_path)
            if comps is None:
                continue
            comps_cache.append(comps)
            actuals.append(float(row["pts"]))
        except Exception:
            continue

    if not comps_cache:
        log.error("No valid rows for grid search")
        return

    actuals_arr = np.array(actuals)
    fga_arr  = np.array([c["fga_pts"]      for c in comps_cache])
    base_arr = np.array([c["baseline_pts"] for c in comps_cache])

    print(f"\n{'='*60}")
    print(f"Alpha grid search | {season} | n={len(actuals_arr)}")
    print(f"{'='*60}")
    print(f"  {'alpha':>6}  {'MAE':>7}  {'bias':>7}  {'RMSE':>7}")
    print(f"  {'-'*35}")

    best_alpha = 0.50
    best_mae   = float("inf")

    for alpha in np.arange(0.25, 0.71, 0.05):
        preds = alpha * fga_arr + (1.0 - alpha) * base_arr
        errs  = preds - actuals_arr
        mae   = float(np.abs(errs).mean())
        bias  = float(errs.mean())
        rmse  = float(np.sqrt((errs**2).mean()))
        flag  = " <-- BEST" if mae < best_mae else ""
        if mae < best_mae:
            best_mae   = mae
            best_alpha = float(alpha)
        print(f"  {alpha:>6.2f}  {mae:>7.3f}  {bias:>+7.3f}  {rmse:>7.3f}{flag}")

    # Compute recommended bias correction at optimal alpha
    preds_best = best_alpha * fga_arr + (1.0 - best_alpha) * base_arr
    bias_best  = float((preds_best - actuals_arr).mean())

    print(f"\n  Optimal alpha:               {best_alpha:.2f}")
    print(f"  Residual bias at alpha={best_alpha:.2f}: {bias_best:+.3f}")
    print(f"  => Set PTS_BLEND_ALPHA = {best_alpha:.2f} in nba_projector.py")
    print(f"  => Set BLEND_BIAS_CORRECTION = {-bias_best:+.3f} in nba_projector.py")
    print(f"{'='*60}\n")


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
    parser.add_argument("--grid-search-alpha", action="store_true",
                        help="Grid-search optimal PTS blend alpha and print recommended constants")
    args = parser.parse_args()

    if args.grid_search_alpha:
        run_alpha_grid_search(
            season=args.season,
            n=args.n,
            min_min=args.min_games,
            db_path=Path(args.db),
            seed=args.seed,
        )
        return

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

    sign  = "+" if out["delta_mae"] < 0 else "-"
    arrow = "BETTER" if out["delta_mae"] < 0 else "WORSE"

    print(f"""
{'='*60}
Evaluation: {out['stat']} | {out['season']} | n={out['n_eval']} (skipped {out['skipped']})
{'='*60}
  Custom   MAE:  {out['custom_mae']:.3f}   RMSE={out['custom_rmse']:.3f}   bias={out['custom_bias']:+.3f}
  Baseline MAE:  {out['baseline_mae']:.3f}   RMSE={out['baseline_rmse']:.3f}   bias={out['baseline_bias']:+.3f}

  Delta (custom vs base): {out['delta_mae']:+.3f} ({out['pct_delta']:+.1f}%)  Custom {arrow} than per-min baseline
{'='*60}
""")


if __name__ == "__main__":
    _main()
