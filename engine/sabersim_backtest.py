"""sabersim_backtest.py -- Full-slate SaberSim vs custom projection comparison.

Reads SaberSim DK CSVs (one per date), looks up actual box-score stats from
projections.db, runs custom projections for the same date, and compares MAE.

Usage:
    python engine/sabersim_backtest.py --csv-dir PATH_TO_SABERSIM_CSVS
    python engine/sabersim_backtest.py --csv-dir PATH [--stat PTS] [--verbose] [--json]

The CSV filenames must contain the date in YYYY-MM-DD format, e.g.:
    NBA_2026-04-29-500pm_DK_Main.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import logging
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR, PROJECT_ROOT
from projections_db import DB_PATH, get_conn
from name_utils import fold_name

log = logging.getLogger("ss_backtest")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

# ---------------------------------------------------------------------------
# SaberSim CSV parser
# ---------------------------------------------------------------------------

_SS_STAT_COLS = {
    "PTS": "PTS",
    "REB": "RB",
    "AST": "AST",
    "3PM": "3PT",
}

_DB_STAT_COLS = {
    "PTS": "pts",
    "REB": "reb",
    "AST": "ast",
    "3PM": "fg3m",
}


def _extract_date(filename: str) -> Optional[str]:
    """Extract YYYY-MM-DD from filename."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else None


def _load_sabersim_csv(path: Path) -> List[dict]:
    """Return list of {name, pts, reb, ast, fg3m} dicts from SaberSim CSV."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip()
            if not name:
                continue
            rec = {"name": name, "name_key": fold_name(name)}
            valid = False
            for stat, col in _SS_STAT_COLS.items():
                val = row.get(col, "").strip()
                try:
                    rec[f"ss_{stat.lower()}"] = float(val)
                    valid = True
                except (ValueError, TypeError):
                    rec[f"ss_{stat.lower()}"] = None
            if valid:
                rows.append(rec)
    return rows


# ---------------------------------------------------------------------------
# DB lookups
# ---------------------------------------------------------------------------

def _get_actuals_for_date(game_date: str, db_path: str) -> Dict[str, dict]:
    """Return {name_key: {pts, reb, ast, fg3m}} for all players on game_date."""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT p.name_key,
               pgs.pts, pgs.reb, pgs.ast, pgs.fg3m
        FROM player_game_stats pgs
        JOIN players p  ON p.player_id  = pgs.player_id
        JOIN games   g  ON g.game_id    = pgs.game_id
        WHERE g.game_date = ? AND pgs.min >= 1
        """,
        (game_date,)
    ).fetchall()
    conn.close()
    return {
        r["name_key"]: {
            "pts":  float(r["pts"]  or 0),
            "reb":  float(r["reb"]  or 0),
            "ast":  float(r["ast"]  or 0),
            "fg3m": float(r["fg3m"] or 0),
        }
        for r in rows
    }


def _get_custom_projs_for_date(game_date: str, db_path: str) -> Dict[str, dict]:
    """Return {name_key: {proj_pts, proj_reb, proj_ast, proj_fg3m}} from
    projections table if populated, else empty."""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT p.name_key,
               pr.proj_pts, pr.proj_reb, pr.proj_ast, pr.proj_fg3m
        FROM projections pr
        JOIN players p ON p.player_id = pr.player_id
        WHERE pr.run_date = ?
        """,
        (game_date,)
    ).fetchall()
    conn.close()
    return {
        r["name_key"]: {
            "proj_pts":  float(r["proj_pts"]  or 0),
            "proj_reb":  float(r["proj_reb"]  or 0),
            "proj_ast":  float(r["proj_ast"]  or 0),
            "proj_fg3m": float(r["proj_fg3m"] or 0),
        }
        for r in rows
    }


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def _mae(errs):
    return float("nan") if not errs else sum(abs(e) for e in errs) / len(errs)

def _rmse(errs):
    return float("nan") if not errs else math.sqrt(sum(e**2 for e in errs) / len(errs))

def _bias(errs):
    return float("nan") if not errs else sum(errs) / len(errs)


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def run_comparison(
    csv_dir: Path,
    stat_filter: Optional[str] = None,
    db_path: str = DB_PATH,
    regen: bool = False,
    verbose: bool = False,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
) -> dict:
    csv_dir = Path(csv_dir)
    csvs = sorted(csv_dir.glob("NBA_*.csv"))
    if not csvs:
        csvs = sorted(csv_dir.glob("*.csv"))

    # Apply date filters
    if date_after or date_before:
        filtered = []
        for p in csvs:
            d = _extract_date(p.name)
            if d:
                if date_after and d < date_after: continue
                if date_before and d > date_before: continue
            filtered.append(p)
        csvs = filtered

    log.info("Found %d SaberSim CSVs in %s", len(csvs), csv_dir)

    stats_to_check = [stat_filter.upper()] if stat_filter else list(_SS_STAT_COLS.keys())

    ss_errors:  Dict[str, List[float]] = {s: [] for s in stats_to_check}
    cus_errors: Dict[str, List[float]] = {s: [] for s in stats_to_check}
    detail_rows: List[dict] = []
    dates_processed = []

    for csv_path in csvs:
        game_date = _extract_date(csv_path.name)
        if not game_date:
            log.warning("Could not parse date from %s — skipping", csv_path.name)
            continue

        log.info("Processing %s (%s) ...", csv_path.name, game_date)
        ss_rows  = _load_sabersim_csv(csv_path)
        actuals  = _get_actuals_for_date(game_date, db_path)

        # Custom projections: try DB first, regen if requested or empty
        custom = _get_custom_projs_for_date(game_date, db_path)
        if regen or not custom:
            log.info("  Regenerating custom projections for %s ...", game_date)
            try:
                from nba_projector import run_projections
                projs = run_projections(
                    game_date=game_date, season="2025-26",
                    implied_totals={}, spreads={},
                    injury_statuses={}, injury_minutes_overrides={},
                    db_path=db_path, persist=False,
                )
                custom = {
                    fold_name(p["player_name"]): {
                        "proj_pts":  p.get("proj_pts", 0),
                        "proj_reb":  p.get("proj_reb", 0),
                        "proj_ast":  p.get("proj_ast", 0),
                        "proj_fg3m": p.get("proj_fg3m", 0),
                    }
                    for p in projs
                }
            except Exception as exc:
                log.error("  Regen failed for %s: %s", game_date, exc)
                custom = {}

        matched = 0
        for player in ss_rows:
            nk = player["name_key"]
            if nk not in actuals:
                continue  # player didn't play or not in DB

            actual = actuals[nk]
            custom_proj = custom.get(nk, {})
            matched += 1

            for stat in stats_to_check:
                ss_key  = f"ss_{stat.lower()}"
                db_key  = _DB_STAT_COLS[stat]
                cus_key = f"proj_{db_key}"

                ss_val  = player.get(ss_key)
                act_val = actual.get(db_key)
                cus_val = custom_proj.get(cus_key)

                if ss_val is None or act_val is None:
                    continue

                err_ss = ss_val - act_val
                ss_errors[stat].append(err_ss)

                err_c = None
                if cus_val is not None:
                    err_c = cus_val - act_val
                    cus_errors[stat].append(err_c)

                if verbose:
                    print(f"  {game_date} {player['name']:25s} {stat:4s}"
                          f"  actual={act_val:5.1f}"
                          f"  ss={ss_val:5.1f}  custom={cus_val!s:5}")

                detail_rows.append({
                    "date": game_date, "player": player["name"],
                    "stat": stat, "actual": act_val,
                    "ss_proj": ss_val, "custom_proj": cus_val,
                    "err_ss": err_ss, "err_c": err_c,
                })

        log.info("  %s: %d players matched", game_date, matched)
        dates_processed.append(game_date)

    # Build results
    result = {
        "dates": sorted(dates_processed),
        "n_csvs": len(dates_processed),
        "n_rows": len(detail_rows),
        "stat_filter": stat_filter or "all",
        "per_stat": {},
        "overall": {},
    }

    all_ss, all_c = [], []
    for stat in stats_to_check:
        se = ss_errors[stat]
        ce = cus_errors[stat]
        all_ss.extend(se)
        all_c.extend(ce)
        result["per_stat"][stat] = {
            "n_ss": len(se), "n_custom": len(ce),
            "ss_mae":    round(_mae(se),  3),
            "ss_rmse":   round(_rmse(se), 3),
            "ss_bias":   round(_bias(se), 3),
            "cus_mae":   round(_mae(ce),  3),
            "cus_rmse":  round(_rmse(ce), 3),
            "cus_bias":  round(_bias(ce), 3),
        }

    result["overall"] = {
        "n_ss": len(all_ss), "n_custom": len(all_c),
        "ss_mae":   round(_mae(all_ss),  3),
        "ss_rmse":  round(_rmse(all_ss), 3),
        "ss_bias":  round(_bias(all_ss), 3),
        "cus_mae":  round(_mae(all_c),   3),
        "cus_rmse": round(_rmse(all_c),  3),
        "cus_bias": round(_bias(all_c),  3),
    }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main():
    parser = argparse.ArgumentParser(
        description="Compare SaberSim vs custom projections across full slates")
    parser.add_argument("--csv-dir", required=True,
                        help="Directory containing SaberSim DK CSV files")
    parser.add_argument("--stat",    default=None,
                        help="Filter to one stat: PTS|REB|AST|3PM")
    parser.add_argument("--db",      default=DB_PATH)
    parser.add_argument("--regen",   action="store_true",
                        help="Always regenerate custom projections (slower)")
    parser.add_argument("--verbose",      action="store_true")
    parser.add_argument("--json",         action="store_true")
    parser.add_argument("--after",  default=None,
                        help="Only include dates >= YYYY-MM-DD")
    parser.add_argument("--before", default=None,
                        help="Only include dates <= YYYY-MM-DD")
    args = parser.parse_args()

    result = run_comparison(
        csv_dir=Path(args.csv_dir),
        stat_filter=args.stat,
        db_path=args.db,
        regen=args.regen,
        verbose=args.verbose,
        date_after=args.after,
        date_before=args.before,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    o = result["overall"]
    print(f"\n{'='*62}")
    print(f"Full-slate backtest | {result['n_csvs']} dates | {result['n_rows']} player-stat rows")
    print(f"Dates: {', '.join(result['dates'])}")
    print(f"{'='*62}")
    print(f"\nOVERALL  (n_ss={o['n_ss']}, n_custom={o['n_custom']})")
    print(f"  SaberSim  MAE={o['ss_mae']:.3f}  RMSE={o['ss_rmse']:.3f}  bias={o['ss_bias']:+.3f}")
    print(f"  Custom    MAE={o['cus_mae']:.3f}  RMSE={o['cus_rmse']:.3f}  bias={o['cus_bias']:+.3f}")
    if o["ss_mae"] and o["cus_mae"]:
        delta = o["ss_mae"] - o["cus_mae"]
        pct   = delta / o["ss_mae"] * 100
        label = "✓ Custom BETTER" if delta > 0 else "✗ Custom WORSE"
        print(f"  Delta: {delta:+.3f} ({pct:+.1f}%)  {label}")

    print(f"\nPER-STAT:")
    for stat, v in result["per_stat"].items():
        delta = v["ss_mae"] - v["cus_mae"]
        pct   = delta / v["ss_mae"] * 100 if v["ss_mae"] else 0
        label = "✓" if delta > 0 else "✗"
        print(f"  {stat:4s}  ss={v['ss_mae']:.3f} (n={v['n_ss']:3d})"
              f"  custom={v['cus_mae']:.3f} (n={v['n_custom']:3d})"
              f"  {label} {pct:+.1f}%"
              f"  bias: ss={v['ss_bias']:+.3f} cus={v['cus_bias']:+.3f}")


if __name__ == "__main__":
    _main()
