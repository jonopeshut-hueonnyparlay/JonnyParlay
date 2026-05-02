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
    get_team_shooting_stats, get_player_season_game_count,
)
from projections_db import get_team_tov_rate
from nba_projector import (
    compute_shooting_rates, compute_per_minute_rates, compute_reb_rates,
    compute_ast_rate, compute_stl_blk_rates,
    EWMA_SPAN, LEAGUE_AVG_PACE, MATCHUP_CLIP,
    PTS_BLEND_ALPHA, BLEND_BIAS_CORRECTION,
    _REB_POS_OREB_PRIOR, _REB_POS_DREB_PRIOR, REB_ALPHA,
    AST_ALPHA, LEAGUE_AVG_TOV_RATE,
    _STL_POS_PRIOR, _STL_PRIOR_N,
    project_minutes, classify_role, _ROLE_MIN_MINUTES, MIN_GAMES_FOR_TIER,
)

# P17 — archetype strata for stratified MAE breakdown.
# Order determines print order in the report.
ROLE_ORDER = ["starter", "sixth_man", "rotation", "spot", "cold_start"]
POS_ORDER  = ["G", "F", "C"]

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


def _get_proj_min(player_id: int, team_id: int, game_date: str,
                  season: str, spread: float | None,
                  db_path: Path) -> tuple[float, str]:
    """Return (projected_minutes, role) using the same logic as project_player().

    P17: also returns role so callers can stratify eval results by archetype.
    Falls back to role prior if history is insufficient.
    """
    df_raw = get_player_recent_games(player_id, game_date, n_games=30,
                                     season_filter=season, db_path=db_path)
    games_on_team = get_player_season_game_count(player_id, season, team_id, db_path)
    b2b = get_player_b2b_context(player_id, game_date, db_path)

    is_cold_start = games_on_team < MIN_GAMES_FOR_TIER
    if is_cold_start or df_raw.empty:
        role     = "cold_start"
        df_clean = df_raw
    else:
        role    = classify_role(df_raw)
        min_min = _ROLE_MIN_MINUTES[role]
        df_clean = df_raw[df_raw["min"] >= min_min].copy()

    return project_minutes(role, df_clean, b2b, spread=spread), role


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


def project_ast(player_id: int, team_id: int, opp_team_id: int,
                position: str, game_date: str,
                season: str, proj_min: float, db_path: Path) -> float | None:
    """Project AST via per-possession rate decomposition (Brief P3, Sec. 3).

    Rate = player_ast / (team_pace * min/48), position-conditional EWMA + Bayesian shrinkage.
    game_pace = (team_pace + opp_pace) / 2 at inference — incorporates opponent tempo.
    """
    df_raw = get_player_recent_games(player_id, game_date, n_games=20, db_path=db_path)
    df = df_raw[df_raw["min"] >= RATE_MIN_MIN].copy()
    if len(df) < 3:
        return None

    pos_group  = _pos_to_group(position)
    team_pace  = get_team_pace(team_id,     season, db_path=db_path)
    opp_pace   = get_team_pace(opp_team_id, season, db_path=db_path)
    game_pace  = (team_pace + opp_pace) / 2.0

    ast_rate = compute_ast_rate(df, team_pace, pos_group)
    proj_poss = game_pace * proj_min / 48.0

    matchup_ast = get_team_def_ratio(opp_team_id, pos_group, "ast", season, db_path=db_path)
    matchup_ast = max(MATCHUP_CLIP[0], min(MATCHUP_CLIP[1], matchup_ast))

    proj_ast_custom = ast_rate * proj_poss * matchup_ast

    rates = compute_per_minute_rates(df)
    baseline_ast = rates.get("ast", 0.0) * proj_min

    blended = AST_ALPHA * proj_ast_custom + (1.0 - AST_ALPHA) * baseline_ast
    return round(max(0.0, blended), 2)


def project_stl(player_id: int, team_id: int, opp_team_id: int,
                position: str, game_date: str, season: str,
                proj_min: float, db_path, *, alpha: float = 1.0):
    """STL projection: per-possession rate (P5) x proj_poss x opp TOV factor (P6).

    P5: compute_stl_blk_rates now takes team_pace and returns per-possession rates.
    Projection: stl_rate * proj_poss * matchup_stl
    """
    df = get_player_recent_games(player_id, game_date, n_games=30,
                                  season_filter=season, db_path=db_path)
    min_min = 8.0
    df = df[df["min"] >= min_min].copy() if not df.empty else df
    pos_group  = _pos_to_group(position)
    team_pace  = get_team_pace(team_id, season, db_path=db_path)
    opp_pace   = get_team_pace(opp_team_id, season, db_path=db_path)
    game_pace  = (team_pace + opp_pace) / 2.0
    proj_poss  = game_pace * proj_min / 48.0
    stl_rate, _ = compute_stl_blk_rates(df, pos_group, team_pace)
    opp_tov    = get_team_tov_rate(opp_team_id, season, db_path)
    opp_tov_fac = float(np.clip(opp_tov / LEAGUE_AVG_TOV_RATE, 0.80, 1.30))
    return max(0.0, stl_rate * proj_poss * opp_tov_fac)


def project_blk(player_id: int, team_id: int, opp_team_id: int,
                position: str, game_date: str, season: str,
                proj_min: float, db_path, *, alpha: float = 1.0):
    """BLK projection: per-possession rate (P5) x proj_poss.

    P5: compute_stl_blk_rates now takes team_pace and returns per-possession rates.
    """
    df = get_player_recent_games(player_id, game_date, n_games=30,
                                  season_filter=season, db_path=db_path)
    min_min = 8.0
    df = df[df["min"] >= min_min].copy() if not df.empty else df
    pos_group  = _pos_to_group(position)
    team_pace  = get_team_pace(team_id, season, db_path=db_path)
    opp_pace   = get_team_pace(opp_team_id, season, db_path=db_path)
    game_pace  = (team_pace + opp_pace) / 2.0
    proj_poss  = game_pace * proj_min / 48.0
    _, blk_rate = compute_stl_blk_rates(df, pos_group, team_pace)
    return max(0.0, blk_rate * proj_poss)


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
                   alpha: float | None = None,
                   use_actual_min: bool = False) -> dict:
    """Evaluate projection accuracy against DB history.

    P12: use_actual_min=False (default) uses projected minutes, giving a
    realistic error surface.  Pass --use-actual-min to recover the old
    rate-only MAE for direct comparison.
    """
    log.info("Sampling %d player-games from %s (min>=%.0f) ...", n, season, min_min)
    sample = sample_games(season, n, min_min, db_path, seed=seed)
    log.info("Got %d rows  [minutes_mode=%s]", len(sample),
             "actual" if use_actual_min else "projected")

    col = STAT_COL.get(stat.upper(), "pts")
    results = []
    skipped = 0

    for i, row in sample.iterrows():
        try:
            actual     = float(row[col])
            actual_min = float(row["min"])
            pid        = int(row["player_id"])
            tid        = int(row["team_id"])
            gdate      = row["game_date"]
            szn        = row["season"]
            pos        = str(row.get("position", "") or "")

            # opponent — guard against NULL
            home_raw = row["home_team_id"]
            away_raw = row["away_team_id"]
            if pd.isna(home_raw) or pd.isna(away_raw):
                opp_tid = 0
            else:
                home_tid = int(home_raw)
                away_tid = int(away_raw)
                opp_tid  = away_tid if tid == home_tid else home_tid

            # P12: projected vs actual minutes; P17: capture role for stratification
            if use_actual_min:
                pmin = actual_min
                role = classify_role(
                    get_player_recent_games(pid, gdate, n_games=30,
                                            season_filter=szn, db_path=db_path)
                )
            else:
                pmin, role = _get_proj_min(pid, tid, gdate, szn, spread=None,
                                           db_path=db_path)

            if stat.upper() == "PTS":
                custom = project_pts(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path, alpha=alpha)
            elif stat.upper() == "3PM":
                custom = project_3pm(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path)
            elif stat.upper() == "REB":
                custom = project_reb(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path)
            elif stat.upper() == "AST":
                custom = project_ast(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path)
            elif stat.upper() == "STL":
                custom = project_stl(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path)
            elif stat.upper() == "BLK":
                custom = project_blk(pid, tid, opp_tid, pos, gdate, szn, pmin,
                                     db_path)
            else:
                custom = project_per_min(pid, gdate, szn, pmin, stat, db_path)

            baseline = project_per_min(pid, gdate, szn, pmin, stat, db_path)

            if custom is None or baseline is None:
                skipped += 1
                continue

            results.append({
                "player":       row["player_name"],
                "date":         gdate,
                "actual":       actual,
                "custom":       custom,
                "baseline":     baseline,
                "actual_min":   actual_min,
                "proj_min":     pmin,
                "min_err":      pmin - actual_min,
                "custom_err":   custom - actual,
                "baseline_err": baseline - actual,
                "role":         role,                      # P17
                "pos_group":    _pos_to_group(pos),        # P17
            })

            if verbose and (i % 20 == 0):
                log.info("  %s  %s  actual=%.1f  custom=%.1f  base=%.1f  "
                         "proj_min=%.1f actual_min=%.1f",
                         row["player_name"], gdate, actual, custom, baseline,
                         pmin, actual_min)
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
    min_mae     = float(df["min_err"].abs().mean())
    min_bias    = float(df["min_err"].mean())

    # P17 — stratified MAE by role and position group
    by_role = _stratify_mae(df, "role", ROLE_ORDER)
    by_pos  = _stratify_mae(df, "pos_group", POS_ORDER)

    return {
        "n_eval":        n_eval,
        "skipped":       skipped,
        "stat":          stat.upper(),
        "season":        season,
        "use_actual_min": use_actual_min,
        "custom_mae":    custom_mae,
        "baseline_mae":  base_mae,
        "custom_bias":   custom_bias,
        "baseline_bias": base_bias,
        "custom_rmse":   custom_rmse,
        "baseline_rmse": base_rmse,
        "delta_mae":     delta_mae,
        "pct_delta":     delta_mae / base_mae * 100 if base_mae > 0 else 0,
        "min_mae":       min_mae,
        "min_bias":      min_bias,
        "by_role":       by_role,   # P17: {role: {"n", "custom_mae", "baseline_mae", "delta_mae"}}
        "by_pos":        by_pos,    # P17: {pos_group: {...}}
    }


def _stratify_mae(df: pd.DataFrame, col: str, order: list[str]) -> dict:
    """P17 — compute per-stratum MAE for custom and baseline projections.

    Returns an ordered dict: {stratum: {"n", "custom_mae", "baseline_mae", "delta_mae"}}.
    Strata with zero rows are omitted.
    """
    out = {}
    for label in order:
        sub = df[df[col] == label]
        if sub.empty:
            continue
        c_mae = float(sub["custom_err"].abs().mean())
        b_mae = float(sub["baseline_err"].abs().mean())
        out[label] = {
            "n":            len(sub),
            "custom_mae":   c_mae,
            "baseline_mae": b_mae,
            "delta_mae":    c_mae - b_mae,
        }
    return out


def _print_stratified(out: dict) -> None:
    """P17 — print stratified MAE breakdown from run_evaluation() result dict."""
    stat = out.get("stat", "?")
    for dim, key, labels in [
        ("Role",     "by_role", ROLE_ORDER),
        ("Position", "by_pos",  POS_ORDER),
    ]:
        strata = out.get(key, {})
        if not strata:
            continue
        print(f"\n  {dim} breakdown ({stat}):")
        print(f"  {'Stratum':<12}  {'n':>5}  {'Custom MAE':>10}  {'Base MAE':>10}  {'Delta':>8}")
        print(f"  {'-'*52}")
        for label in labels:
            s = strata.get(label)
            if s is None:
                continue
            arrow = "▲" if s["delta_mae"] > 0 else "▼"
            print(f"  {label:<12}  {s['n']:>5}  {s['custom_mae']:>10.3f}  "
                  f"{s['baseline_mae']:>10.3f}  {s['delta_mae']:>+7.3f}{arrow}")


def run_alpha_grid_search(season: str, n: int, min_min: float,
                          db_path: Path, seed: int | None = None,
                          use_actual_min: bool = False) -> None:
    """Grid-search PTS_BLEND_ALPHA over [0.25, 0.70] to find MAE-optimal weight.

    Runs on the same sample (seed-fixed) so results are directly comparable.
    Bias correction is NOT applied during grid search so alpha absorbs it;
    re-fit BLEND_BIAS_CORRECTION against residuals AFTER locking alpha.
    P12: use projected minutes by default (use_actual_min=False).
    """
    log.info("Alpha grid search: sampling %d games from %s ...", n, season)
    sample = sample_games(season, n, min_min, db_path, seed=seed)
    log.info("Got %d rows  [minutes_mode=%s]", len(sample),
             "actual" if use_actual_min else "projected")

    # Pre-compute FGA-decomp components and baseline for every row
    comps_cache = []
    actuals = []
    for _, row in sample.iterrows():
        try:
            pid  = int(row["player_id"])
            tid  = int(row["team_id"])
            gdate = row["game_date"]
            szn   = row["season"]
            pos   = str(row.get("position", "") or "")
            home_raw = row["home_team_id"]
            away_raw = row["away_team_id"]
            if pd.isna(home_raw) or pd.isna(away_raw):
                opp_tid = 0
            else:
                home_tid = int(home_raw)
                away_tid = int(away_raw)
                opp_tid  = away_tid if tid == home_tid else home_tid

            # P12: use projected or actual minutes
            if use_actual_min:
                pmin = float(row["min"])
            else:
                pmin, _ = _get_proj_min(pid, tid, gdate, szn, spread=None,
                                        db_path=db_path)  # role not needed in grid search

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
    parser.add_argument("--use-actual-min", action="store_true",
                        help="Use actual minutes (old behaviour). Default: projected minutes (P12)")
    args = parser.parse_args()

    if args.grid_search_alpha:
        run_alpha_grid_search(
            season=args.season,
            n=args.n,
            min_min=args.min_games,
            db_path=Path(args.db),
            seed=args.seed,
            use_actual_min=args.use_actual_min,
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
        use_actual_min=args.use_actual_min,
    )

    if not out:
        sys.exit(1)

    sign  = "+" if out["delta_mae"] < 0 else "-"
    arrow = "BETTER" if out["delta_mae"] < 0 else "WORSE"
    min_label = "actual" if out["use_actual_min"] else "projected"

    print(f"""
{'='*60}
Evaluation: {out['stat']} | {out['season']} | n={out['n_eval']} (skipped {out['skipped']})
minutes_mode: {min_label}
{'='*60}
  Custom   MAE:  {out['custom_mae']:.3f}   RMSE={out['custom_rmse']:.3f}   bias={out['custom_bias']:+.3f}
  Baseline MAE:  {out['baseline_mae']:.3f}   RMSE={out['baseline_rmse']:.3f}   bias={out['baseline_bias']:+.3f}

  Delta (custom vs base): {out['delta_mae']:+.3f} ({out['pct_delta']:+.1f}%)  Custom {arrow} than per-min baseline

  Minutes MAE:   {out['min_mae']:.3f}   bias={out['min_bias']:+.3f}
{'='*60}
""")
    _print_stratified(out)  # P17 — archetype stratification


if __name__ == "__main__":
    _main()
