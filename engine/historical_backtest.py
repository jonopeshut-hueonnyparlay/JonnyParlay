"""historical_backtest.py — retrospective backtest on regular-season games.

Samples N game dates from 2024-25 Regular Season, runs project_player()
on all players who actually played that day (using only data before that date),
and computes MAE vs actuals.

Usage:
    JONNYPARLAY_ROOT=/path/to/JonnyParlay python historical_backtest.py [--n-dates N] [--seed S] [--verbose]

Output: per-stat MAE/bias table + overall summary, role-tier breakdown,
        and cold_start vs known-player split.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
import os
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# Path setup — works whether run from outputs/ or JonnyParlay/engine/
# ---------------------------------------------------------------------------
_ROOT = Path(os.environ.get("JONNYPARLAY_ROOT", "")).resolve()
if not _ROOT or not (_ROOT / "engine" / "nba_projector.py").exists():
    # Try common locations
    for _candidate in [
        Path(__file__).resolve().parent.parent / "JonnyParlay",
        Path.home() / "Documents" / "JonnyParlay",
    ]:
        if (_candidate / "engine" / "nba_projector.py").exists():
            _ROOT = _candidate
            break
    else:
        sys.exit("ERROR: Cannot find JonnyParlay root. Set JONNYPARLAY_ROOT env var.")

_ENGINE = _ROOT / "engine"
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from nba_projector import project_player, CURRENT_SEASON
from projections_db import DB_PATH, get_conn

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mae(errors):
    return float("nan") if not errors else sum(abs(e) for e in errors) / len(errors)

def _bias(errors):
    return float("nan") if not errors else sum(errors) / len(errors)

def _rmse(errors):
    return float("nan") if not errors else math.sqrt(sum(e**2 for e in errors) / len(errors))


# ---------------------------------------------------------------------------
# Sample regular-season dates
# ---------------------------------------------------------------------------

def get_regular_season_dates(season: str, db_path: Path) -> list[str]:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT DISTINCT game_date FROM games WHERE season=? AND season_type='Regular Season' ORDER BY game_date",
        (season,)
    ).fetchall()
    conn.close()
    return [r["game_date"] for r in rows]


def get_games_on_date(game_date: str, db_path: Path) -> list[dict]:
    """Return list of {game_id, home_team_id, away_team_id, season, season_type}."""
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT game_id, home_team_id, away_team_id, season, season_type FROM games WHERE game_date=?",
        (game_date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_players_in_game(game_id: str, db_path: Path) -> list[dict]:
    """Return players who played in this game with their team, actual stats, and actual minutes."""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT pgs.player_id, pgs.team_id, pgs.min,
               pgs.pts, pgs.ast, pgs.reb, pgs.fg3m, pgs.blk, pgs.stl, pgs.tov,
               p.name, p.position
        FROM player_game_stats pgs
        JOIN players p ON p.player_id = pgs.player_id
        WHERE pgs.game_id = ? AND pgs.min >= 5.0
        """,
        (game_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Main backtest runner
# ---------------------------------------------------------------------------

STAT_KEYS = [
    ("PTS",  "pts",  "proj_pts"),
    ("AST",  "ast",  "proj_ast"),
    ("REB",  "reb",  "proj_reb"),
    ("3PM",  "fg3m", "proj_fg3m"),
    ("BLK",  "blk",  "proj_blk"),
    ("STL",  "stl",  "proj_stl"),
]


def run_historical_backtest(
    n_dates: int = 30,
    seed: int = 42,
    season: str = "2024-25",
    db_path: Path = DB_PATH,
    verbose: bool = False,
):
    print(f"\nHistorical backtest: season={season}, n_dates={n_dates}, seed={seed}")
    print(f"DB: {db_path}\n")

    all_dates = get_regular_season_dates(season, db_path)
    if not all_dates:
        print(f"ERROR: No regular-season dates found for {season}")
        return

    print(f"Available regular-season dates: {len(all_dates)}  ({all_dates[0]} to {all_dates[-1]})")

    # Sample evenly across the season (not just random, to avoid clustering)
    rng = random.Random(seed)
    if n_dates >= len(all_dates):
        sampled_dates = all_dates
    else:
        # Stratified: divide into n_dates buckets, pick one from each
        bucket_size = len(all_dates) / n_dates
        sampled_dates = sorted(
            all_dates[int(rng.uniform(i * bucket_size, (i + 1) * bucket_size))]
            for i in range(n_dates)
        )

    print(f"Sampled {len(sampled_dates)} dates: {sampled_dates[0]} to {sampled_dates[-1]}")

    # Accumulators
    errors_by_stat = defaultdict(list)   # stat -> list of (error, is_cold_start, role, proj)
    errors_by_role = defaultdict(list)   # role_tier -> list of (abs_error, stat_name, proj) tuples (T4)
    errors_raw     = []
    errors_adj     = []
    role_counts    = defaultdict(int)
    cold_start_n   = 0
    total_players  = 0
    skipped        = 0
    proj_errors    = 0
    # Minutes tracking: list of (proj_min, act_min, role) for players with min >= 5
    min_records    = []

    for date_idx, game_date in enumerate(sampled_dates):
        games = get_games_on_date(game_date, db_path)
        print(f"[{date_idx+1}/{len(sampled_dates)}] {game_date}: {len(games)} games", flush=True)
        if verbose:
            print(f"\n[{date_idx+1}/{len(sampled_dates)}] {game_date}: {len(games)} games")

        for game in games:
            game_id   = game["game_id"]
            home_tid  = game["home_team_id"]
            away_tid  = game["away_team_id"]
            season_type = game["season_type"]
            players = get_players_in_game(game_id, db_path)

            for pdata in players:
                pid      = pdata["player_id"]
                tid      = pdata["team_id"]
                opp_tid  = away_tid if tid == home_tid else home_tid
                is_home  = (tid == home_tid)
                name     = pdata["name"]
                pos      = pdata["position"] or "G"
                act_min  = pdata["min"]

                total_players += 1

                try:
                    proj = project_player(
                        player_id=pid,
                        player_name=name,
                        position=pos,
                        team_id=tid,
                        opp_team_id=opp_tid,
                        game_id=game_id,
                        game_date=game_date,
                        season=season,
                        season_type=season_type,
                        implied_total=None,
                        spread=None,
                        injury_status="",
                        injury_minutes_override=None,
                        is_home=is_home,
                        db_path=db_path,
                    )
                except Exception as e:
                    proj_errors += 1
                    if verbose:
                        print(f"  ERROR projecting {name}: {e}")
                    continue

                if proj is None:
                    skipped += 1
                    continue

                role = proj.get("role_tier", "unknown")
                is_cold = (role == "cold_start")
                proj_min = proj.get("proj_min", 0.0) or 0.0
                role_counts[role] += 1
                if is_cold:
                    cold_start_n += 1

                # Minutes tracking
                if proj_min > 0 and act_min and act_min > 0:
                    min_records.append((proj_min, float(act_min), role))

                for stat_name, actual_col, proj_col in STAT_KEYS:
                    actual_val = pdata.get(actual_col)
                    proj_val   = proj.get(proj_col)

                    if actual_val is None or proj_val is None:
                        continue

                    actual_f = float(actual_val)
                    proj_f   = float(proj_val)
                    err_raw  = proj_f - actual_f
                    errors_raw.append(err_raw)
                    errors_by_stat[stat_name].append((err_raw, is_cold, role, proj_f))
                    errors_by_role[role].append((err_raw, stat_name, proj_f))

                    # Rate-adjusted: what would player have produced at their
                    # per-minute rate in OUR projected minutes?
                    if act_min and act_min > 0 and proj_min > 0:
                        ra_actual = actual_f / act_min * proj_min
                        err_adj   = proj_f - ra_actual
                        errors_adj.append(err_adj)

                if verbose:
                    print(f"  {name:25s} role={role:12s} proj_min={proj_min:.1f}  "
                          f"PTS: proj={proj.get('proj_pts', '?'):.1f} act={pdata.get('pts', '?')}")

    # ---------------------------------------------------------------------------
    # Report
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print(f"RESULTS: {season} Regular Season Retrospective Backtest")
    print("=" * 65)
    print(f"Dates sampled_dates:      {len(sampled_dates)}")
    print(f"Total player-games: {total_players}")
    print(f"Projections run:    {total_players - skipped - proj_errors}")
    print(f"Skipped (proj=None):{skipped}")
    print(f"Errors:             {proj_errors}")
    print(f"Cold-start:         {cold_start_n}  ({100*cold_start_n/max(1,total_players-skipped-proj_errors):.1f}%)")

    print("\nRole breakdown:")
    for role, cnt in sorted(role_counts.items(), key=lambda x: -x[1]):
        print(f"  {role:15s}: {cnt}")

    # Overall MAE
    all_raw_errors = [e for errs in errors_by_stat.values() for (e, _, _, _) in errs]
    cold_raw = [e for errs in errors_by_stat.values() for (e, ic, _, _) in errs if ic]
    known_raw = [e for errs in errors_by_stat.values() for (e, ic, _, _) in errs if not ic]

    print(f"\nOverall MAE (raw):             {_mae(all_raw_errors):.3f}  (n={len(all_raw_errors)})")
    print(f"Overall MAE (rate-adj):        {_mae(errors_adj):.3f}  (n={len(errors_adj)})")
    print(f"Overall bias (raw):            {_bias(all_raw_errors):+.3f}")
    print(f"Overall bias (rate-adj):       {_bias(errors_adj):+.3f}")
    print(f"\nKnown-player MAE (non cold):   {_mae(known_raw):.3f}  (n={len(known_raw)})")
    print(f"Cold-start MAE:                {_mae(cold_raw):.3f}  (n={len(cold_raw)})")

    print("\nPer-stat breakdown (raw errors):")
    print(f"  {'Stat':6s}  {'MAE':>7s}  {'Bias':>7s}  {'RMSE':>7s}  {'MeanProj':>9s}  {'Scalar':>7s}  {'n':>5s}  {'n_cold':>6s}  {'cold_MAE':>8s}")
    for stat_name, _, _ in STAT_KEYS:
        errs  = errors_by_stat[stat_name]
        if not errs:
            continue
        all_e    = [e for e, _, _, _ in errs]
        cold_e   = [e for e, ic, _, _ in errs if ic]
        projs    = [p for _, _, _, p in errs]
        mean_p   = sum(projs) / len(projs) if projs else 0.0
        bias_val = _bias(all_e)
        # Suggested scalar to eliminate current bias: scalar = 1 - bias/mean_proj
        # (bias = proj - actual, so actual = proj - bias; to hit actual: proj * scalar = actual)
        scalar   = (mean_p - bias_val) / mean_p if mean_p > 0 else 1.0
        print(f"  {stat_name:6s}  {_mae(all_e):7.3f}  {bias_val:+7.3f}  {_rmse(all_e):7.3f}"
              f"  {mean_p:9.3f}  {scalar:7.4f}"
              f"  {len(all_e):5d}  {len(cold_e):6d}  {_mae(cold_e) if cold_e else float('nan'):8.3f}")

    # ---------------------------------------------------------------------------
    # T4: Bias by role tier
    # ---------------------------------------------------------------------------
    if errors_by_role:
        print("\n" + "=" * 65)
        print("BIAS BY ROLE TIER  (T4, 2026-05-02)")
        print("=" * 65)
        print(f"  {'Role':15s}  {'MAE':>7s}  {'Bias':>7s}  {'RMSE':>7s}  {'n':>5s}")
        role_order = ["starter", "sixth_man", "rotation", "spot", "cold_start", "unknown"]
        seen_roles = set(errors_by_role.keys())
        ordered = role_order + [r for r in sorted(seen_roles) if r not in role_order]
        for role in ordered:
            errs_r = errors_by_role.get(role)
            if not errs_r:
                continue
            all_e = [e for e, _, _ in errs_r]
            print(f"  {role:15s}  {_mae(all_e):7.3f}  {_bias(all_e):+7.3f}  {_rmse(all_e):7.3f}  {len(all_e):5d}")

        # Per-stat × per-role for PTS (highest volume, most meaningful to inspect)
        print(f"\n  PTS bias by role tier:")
        print(f"  {'Role':15s}  {'Bias':>7s}  {'MAE':>7s}  {'MeanProj':>9s}  {'n':>5s}")
        for role in ordered:
            errs_r = errors_by_role.get(role)
            if not errs_r:
                continue
            pts_e = [(e, p) for e, st, p in errs_r if st == "PTS"]
            if not pts_e:
                continue
            all_e = [e for e, _ in pts_e]
            mean_p = sum(p for _, p in pts_e) / len(pts_e)
            print(f"  {role:15s}  {_bias(all_e):+7.3f}  {_mae(all_e):7.3f}  {mean_p:9.3f}  {len(all_e):5d}")

    # ---------------------------------------------------------------------------
    # T4: Projection magnitude bucketing (PTS) — is bias worse at high/low proj?
    # ---------------------------------------------------------------------------
    pts_errs = errors_by_stat.get("PTS", [])
    if pts_errs:
        print("\n" + "=" * 65)
        print("PTS BIAS BY PROJECTION MAGNITUDE  (T4, 2026-05-02)")
        print("=" * 65)
        # Buckets: <8, 8-12, 12-16, 16-20, 20-25, 25+
        buckets = [
            ("<8",    lambda p: p < 8),
            ("8-12",  lambda p: 8 <= p < 12),
            ("12-16", lambda p: 12 <= p < 16),
            ("16-20", lambda p: 16 <= p < 20),
            ("20-25", lambda p: 20 <= p < 25),
            ("25+",   lambda p: p >= 25),
        ]
        print(f"  {'Bucket':8s}  {'MAE':>7s}  {'Bias':>7s}  {'n':>5s}")
        for label, fn in buckets:
            bucket_e = [e for e, _, _, p in pts_errs if fn(p)]
            if not bucket_e:
                continue
            print(f"  {label:<8s}  {_mae(bucket_e):7.3f}  {_bias(bucket_e):+7.3f}  {len(bucket_e):5d}")

    # ---------------------------------------------------------------------------
    # Minutes analysis
    # ---------------------------------------------------------------------------
    if min_records:
        print("\n" + "=" * 65)
        print("MINUTES MODEL ANALYSIS")
        print("=" * 65)

        ratios = [act / proj for proj, act, _ in min_records]
        mean_ratio = sum(ratios) / len(ratios)
        mean_bias  = sum(act - proj for proj, act, _ in min_records) / len(min_records)
        sorted_r   = sorted(ratios)
        n          = len(sorted_r)
        p25 = sorted_r[int(0.25 * n)]
        p50 = sorted_r[int(0.50 * n)]
        p75 = sorted_r[int(0.75 * n)]

        print(f"  Player-games with valid proj_min: {n}")
        print(f"  Mean ratio  act_min/proj_min: {mean_ratio:.4f}  (>1 = underprojecting minutes)")
        print(f"  Mean bias   act_min-proj_min: {mean_bias:+.3f} min")
        print(f"  Percentiles (ratio): p25={p25:.3f}  p50={p50:.3f}  p75={p75:.3f}")
        print(f"\n  Suggested scalar for nba_projector.py: {mean_ratio:.4f}")
        print(f"  (Apply as: proj_min *= {mean_ratio:.4f} before stat calculation)")

        # By role tier
        roles_seen = sorted(set(r for _, _, r in min_records))
        print(f"\n  {'Role':15s}  {'n':>5s}  {'mean_ratio':>10s}  {'mean_bias':>10s}")
        for role in roles_seen:
            recs = [(p, a) for p, a, r in min_records if r == role]
            r_ratios = [a / p for p, a in recs]
            r_bias   = sum(a - p for p, a in recs) / len(recs)
            print(f"  {role:15s}  {len(recs):5d}  {sum(r_ratios)/len(r_ratios):10.4f}  {r_bias:+10.3f}")

    # Comparison to known playoff benchmark
    print("\n" + "-" * 65)
    print("Reference benchmarks (from playoff backtest Apr 18-29 2026):")
    print("  Custom adj MAE: 3.436  |  SaberSim raw MAE: 3.254")
    print("  Bias: -0.108  |  Cold-start: 34% of projections")
    print("-" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-dates", type=int, default=30)
    parser.add_argument("--seed",    type=int, default=42)
    parser.add_argument("--season",  default="2024-25")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--db",      default=None)
    args = parser.parse_args()

    run_historical_backtest(
        n_dates=args.n_dates,
        seed=args.seed,
        season=args.season,
        verbose=args.verbose,
        db_path=Path(args.db) if args.db else DB_PATH,
    )
