"""backtest_projections.py -- MAE + CLV comparison harness.

Compares custom projection engine vs SaberSim projections across historical
graded picks in pick_log.csv.

Usage:
    python engine/backtest_projections.py [options]

Options:
    --since YYYY-MM-DD   Start date (default: 30 days ago)
    --until YYYY-MM-DD   End date (default: today)
    --sport NBA|NHL      Filter by sport (default: NBA)
    --stat PTS|AST|...   Filter by stat (default: all props)
    --db PATH            SQLite DB path (default: data/projections.db)
    --csv PATH           pick_log.csv path (default: data/pick_log.csv)
    --json               Output as JSON
    --regen              Regenerate custom projections (slow: hits DB)
    --verbose            Print per-pick detail
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io as _io
import json
import logging
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR, PROJECT_ROOT
from projections_db import DB_PATH, get_conn, get_player_recent_games
from name_utils import fold_name

log = logging.getLogger("backtest")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

# ---------------------------------------------------------------------------
# pick_log reader
# ---------------------------------------------------------------------------

def _load_pick_log(csv_path: Path) -> pd.DataFrame:
    """Load pick_log.csv, filter to graded prop picks.

    Strips rows with unterminated quoted fields (FUSE-truncated legs JSON).
    """
    raw = Path(csv_path).read_bytes()
    lines = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")

    clean_lines: list = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Odd unescaped-quote count = unterminated field
        q = stripped.count(b'"') - stripped.count(b'""') * 2
        if q % 2 != 0:
            log.debug("Skipping malformed line: %s", stripped[:60])
            continue
        clean_lines.append(line)

    buf = _io.StringIO("\n".join(l.decode("utf-8", errors="replace") for l in clean_lines))
    df = pd.read_csv(buf, dtype=str, on_bad_lines="skip", engine="python")
    df.columns = [c.strip().lower() for c in df.columns]

    # Only graded picks with actual results
    df = df[df.get("result", pd.Series()).isin(["W", "L"])].copy()
    # Props only
    prop_stats = {"PTS", "AST", "REB", "3PM", "SOG", "BLK", "STL"}
    if "stat" in df.columns:
        df = df[df["stat"].isin(prop_stats)].copy()
    # Must have projection value
    if "proj" in df.columns:
        df = df[pd.to_numeric(df["proj"], errors="coerce").notna()].copy()
        df["proj"] = pd.to_numeric(df["proj"])

    return df


# ---------------------------------------------------------------------------
# Fetch actual box-score stat from DB
# ---------------------------------------------------------------------------

_STAT_COL_MAP = {
    "PTS": "pts",
    "AST": "ast",
    "REB": "reb",
    "3PM": "fg3m",
    "SOG": None,
    "BLK": "blk",
    "STL": "stl",
}


def _get_actual_stat(player_name, stat, game_date, db_path):
    col = _STAT_COL_MAP.get(stat.upper())
    if col is None:
        return None
    conn = get_conn(db_path)
    name_key = fold_name(player_name)
    row = conn.execute(
        "SELECT player_id FROM players WHERE name_key=?", (name_key,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    pid = row["player_id"]
    # game_date lives in games table -- join through game_id
    stat_row = conn.execute(
        f"SELECT pgs.{col} FROM player_game_stats pgs"
        " JOIN games g ON g.game_id = pgs.game_id"
        " WHERE pgs.player_id=? AND g.game_date=?",
        (pid, game_date)
    ).fetchone()
    conn.close()
    if stat_row is None:
        return None
    val = stat_row[col]
    return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# Custom projection lookup (from projections table or regen)
# ---------------------------------------------------------------------------

_PROJ_COL_MAP = {
    "PTS": "proj_pts",
    "AST": "proj_ast",
    "REB": "proj_reb",
    "3PM": "proj_fg3m",
    "BLK": "proj_blk",
    "STL": "proj_stl",
}


def _get_custom_proj(player_name, stat, game_date, db_path):
    col = _PROJ_COL_MAP.get(stat.upper())
    if col is None:
        return None
    conn = get_conn(db_path)
    name_key = fold_name(player_name)
    row = conn.execute(
        "SELECT player_id FROM players WHERE name_key=?", (name_key,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    pid = row["player_id"]
    proj_row = conn.execute(
        f"SELECT {col} FROM projections WHERE player_id=? AND run_date=?",
        (pid, game_date)
    ).fetchone()
    conn.close()
    if proj_row is None:
        return None
    val = proj_row[col]
    return float(val) if val is not None else None


_proj_cache: Dict[str, object] = {}

def _regenerate_projections(game_date, db_path):
    if game_date in _proj_cache:
        return _proj_cache[game_date]
    try:
        from nba_projector import run_projections
    except ImportError:
        log.error("nba_projector not available")
        return []
    log.info("Regenerating projections for %s...", game_date)
    projs = run_projections(
        game_date=game_date, season="2025-26",
        implied_totals={}, spreads={},
        injury_statuses={}, injury_minutes_overrides={},
        db_path=db_path, persist=True,
    )
    _proj_cache[game_date] = projs
    name_map = {fold_name(p["player_name"]): p for p in projs}
    _proj_cache[f"{game_date}_map"] = name_map
    return projs


def _get_regen_proj(player_name, stat, game_date, db_path):
    _regenerate_projections(game_date, db_path)
    name_map = _proj_cache.get(f"{game_date}_map", {})
    p = name_map.get(fold_name(player_name))
    if p is None:
        return None
    col = _PROJ_COL_MAP.get(stat.upper())
    return p.get(col) if col else None


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def _mae(errors):
    return float("nan") if not errors else sum(abs(e) for e in errors) / len(errors)

def _rmse(errors):
    return float("nan") if not errors else math.sqrt(sum(e**2 for e in errors) / len(errors))

def _bias(errors):
    return float("nan") if not errors else sum(errors) / len(errors)


def _clv_stats(df):
    if "clv" not in df.columns:
        return {"mean_clv": float("nan"), "positive_clv_rate": float("nan"), "n_clv": 0}
    clv = pd.to_numeric(df["clv"], errors="coerce").dropna()
    if clv.empty:
        return {"mean_clv": float("nan"), "positive_clv_rate": float("nan"), "n_clv": 0}
    return {
        "mean_clv": round(float(clv.mean()), 4),
        "positive_clv_rate": round(float((clv > 0).mean()), 4),
        "n_clv": int(len(clv)),
    }


# ---------------------------------------------------------------------------
# Main backtest runner
# ---------------------------------------------------------------------------

def run_backtest(
    since, until,
    sport="NBA",
    stat_filter=None,
    db_path=DB_PATH,
    csv_path=None,
    regen=False,
    verbose=False,
):
    if csv_path is None:
        csv_path = DATA_DIR / "pick_log.csv"

    log.info("Loading pick log from %s", csv_path)
    df = _load_pick_log(Path(csv_path))

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[(df["date"] >= since) & (df["date"] <= until)]

    if "sport" in df.columns:
        df = df[df["sport"].str.upper() == sport.upper()].copy()

    if stat_filter and "stat" in df.columns:
        df = df[df["stat"].str.upper() == stat_filter.upper()].copy()

    log.info("Picks to analyze: %d", len(df))
    if df.empty:
        return {"error": "No graded picks found in range"}

    sabersim_errors, custom_errors = [], []
    detail_rows = []

    for _, pick in df.iterrows():
        player  = str(pick.get("player", ""))
        stat    = str(pick.get("stat", ""))
        date_s  = str(pick["date"].date()) if hasattr(pick.get("date"), "date") else str(pick.get("date", ""))
        ss_proj = float(pick["proj"]) if "proj" in pick and pd.notna(pick.get("proj")) else None

        actual = _get_actual_stat(player, stat, date_s, db_path)
        if actual is None:
            continue

        err_ss = None
        if ss_proj is not None:
            err_ss = ss_proj - actual
            sabersim_errors.append(err_ss)

        custom_proj = (_get_regen_proj if regen else _get_custom_proj)(player, stat, date_s, db_path)
        err_c = None
        if custom_proj is not None:
            err_c = custom_proj - actual
            custom_errors.append(err_c)

        if verbose:
            print(f"  {date_s} {player:25s} {stat:4s}  actual={actual:.1f}"
                  f"  ss={ss_proj or 'N/A'!s:5}  custom={custom_proj or 'N/A'!s:5}")

        detail_rows.append({"date": date_s, "player": player, "stat": stat,
                             "actual": actual, "sabersim_proj": ss_proj,
                             "custom_proj": custom_proj,
                             "err_ss": err_ss, "err_c": err_c})

    result = {
        "period": {"since": since, "until": until},
        "sport": sport,
        "stat_filter": stat_filter or "all",
        "n_picks": len(df),
        "n_actuals_found": len(detail_rows),
        "sabersim": {
            "n": len(sabersim_errors),
            "mae":  round(_mae(sabersim_errors),  3),
            "rmse": round(_rmse(sabersim_errors), 3),
            "bias": round(_bias(sabersim_errors), 3),
        },
        "custom": {
            "n": len(custom_errors),
            "mae":  round(_mae(custom_errors),  3),
            "rmse": round(_rmse(custom_errors), 3),
            "bias": round(_bias(custom_errors), 3),
        },
        "clv": _clv_stats(df),
        "win_rate": (
            round(float((df["result"] == "W").mean()), 4)
            if "result" in df.columns and not df.empty else float("nan")
        ),
    }

    if stat_filter is None and detail_rows:
        breakdown: Dict[str, dict] = {}
        for row in detail_rows:
            s = row["stat"]
            if s not in breakdown:
                breakdown[s] = {"ss": [], "c": []}
            if row["err_ss"] is not None:
                breakdown[s]["ss"].append(row["err_ss"])
            if row["err_c"] is not None:
                breakdown[s]["c"].append(row["err_c"])
        result["per_stat"] = {
            s: {
                "sabersim_mae": round(_mae(v["ss"]), 3),
                "custom_mae":   round(_mae(v["c"]),  3),
                "n_ss": len(v["ss"]), "n_c": len(v["c"]),
            }
            for s, v in breakdown.items()
        }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main():
    today      = datetime.date.today()
    thirty_ago = today - datetime.timedelta(days=30)

    parser = argparse.ArgumentParser(description="Backtest custom projections vs SaberSim")
    parser.add_argument("--since",   default=str(thirty_ago))
    parser.add_argument("--until",   default=str(today))
    parser.add_argument("--sport",   default="NBA")
    parser.add_argument("--stat",    default=None)
    parser.add_argument("--db",      default=DB_PATH)
    parser.add_argument("--csv",     default=None)
    parser.add_argument("--json",    action="store_true")
    parser.add_argument("--regen",   action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    result = run_backtest(
        since=args.since, until=args.until,
        sport=args.sport, stat_filter=args.stat,
        db_path=args.db,
        csv_path=Path(args.csv) if args.csv else None,
        regen=args.regen, verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"\n{'='*60}")
    print(f"Backtest: {result['sport']} | {result.get('stat_filter','all').upper()} | "
          f"{result['period']['since']} → {result['period']['until']}")
    print(f"{'='*60}")
    print(f"Graded picks:     {result['n_picks']}")
    print(f"Actuals found:    {result['n_actuals_found']}")
    print(f"Win rate:         {result.get('win_rate', float('nan')):.1%}")

    clv = result["clv"]
    print(f"\nCLV (n={clv['n_clv']}):")
    print(f"  Mean CLV:       {clv['mean_clv']:+.4f}")
    print(f"  CLV+ rate:      {clv['positive_clv_rate']:.1%}" if clv['n_clv'] else "  CLV+ rate:      N/A")

    ss = result["sabersim"]
    cu = result["custom"]
    print(f"\nMAE comparison (n_ss={ss['n']}, n_custom={cu['n']}):")
    print(f"  SaberSim MAE:   {ss['mae']:.3f}  RMSE={ss['rmse']:.3f}  bias={ss['bias']:+.3f}")
    print(f"  Custom MAE:     {cu['mae']:.3f}  RMSE={cu['rmse']:.3f}  bias={cu['bias']:+.3f}")

    if ss['mae'] and cu['mae'] and ss['n'] and cu['n']:
        delta = ss['mae'] - cu['mae']
        pct   = delta / ss['mae'] * 100
        print(f"\n  Delta: {delta:+.3f} ({pct:+.1f}%)  "
              f"{'✓ Custom BETTER' if delta > 0 else '✗ Custom WORSE'}")

    if "per_stat" in result:
        print(f"\nPer-stat MAE:")
        for stat, v in sorted(result["per_stat"].items()):
            print(f"  {stat:5s}  ss={v['sabersim_mae']:.3f} (n={v['n_ss']})  "
                  f"custom={v['custom_mae']:.3f} (n={v['n_c']})")


if __name__ == "__main__":
    _main()
