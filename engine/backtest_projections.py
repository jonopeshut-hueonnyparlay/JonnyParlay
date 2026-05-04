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

P0 note (2026-05-01):
    Custom MAE is now reported in two forms:
      raw       -- |custom_proj - actual_stat|   (confounds minutes + rate error)
      adj       -- |custom_proj - (actual_stat / actual_min * proj_min)|
                   Holds minutes constant at what we projected, isolating rate accuracy.
    SaberSim MAE remains raw (their projected minutes are not stored).
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
    CRIT-3: uses csv.reader for RFC-4180-correct field validation instead of
    manual byte-level quote counting (which overcounted for escaped ""pairs).
    """
    raw_text = Path(csv_path).read_bytes().decode("utf-8", errors="replace")
    raw_lines = raw_text.splitlines()

    clean_rows: list = []
    n_malformed = 0
    expected_cols: int | None = None

    for raw_line in raw_lines:
        if not raw_line.strip():
            continue
        # CRIT-3: parse each line in isolation so unterminated quotes can't
        # cause csv.reader to consume subsequent lines as field continuations.
        try:
            row = next(iter(csv.reader([raw_line])))
        except (csv.Error, StopIteration) as exc:
            log.warning("CRIT-3: csv.Error on pick_log line (%s): %s", exc, raw_line[:80])
            n_malformed += 1
            continue

        if expected_cols is None:
            # First non-blank line is the header
            expected_cols = len(row)
            clean_rows.append(row)
            continue

        if len(row) != expected_cols:
            # H25: rows with exactly one fewer column are legacy 27-col rows
            # (before the `legs` column was added in schema_version 3). Pad
            # with an empty trailing field rather than dropping them silently.
            if len(row) == expected_cols - 1:
                row = row + [""]
                log.debug(
                    "H25: padded legacy %d-col row to %d cols: %s",
                    expected_cols - 1, expected_cols, raw_line[:80],
                )
            else:
                # Wrong field count → FUSE-truncated or otherwise malformed
                log.warning(
                    "CRIT-3: Skipping malformed pick_log row (%d fields, expected %d): %s",
                    len(row), expected_cols, raw_line[:80],
                )
                n_malformed += 1
                continue

        clean_rows.append(row)

    if n_malformed:
        log.warning("CRIT-3: %d malformed row(s) dropped — check for FUSE truncation", n_malformed)

    if len(clean_rows) < 2:
        # Header only or completely empty
        return pd.DataFrame()

    # Rebuild a clean CSV buffer from the validated rows
    out = _io.StringIO()
    _writer = csv.writer(out)
    for row in clean_rows:
        _writer.writerow(row)
    out.seek(0)
    # H25: all rows in clean_rows now have exactly expected_cols fields;
    # on_bad_lines="error" catches any remaining inconsistency loudly.
    df = pd.read_csv(out, dtype=str, on_bad_lines="error", engine="python")
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
# Fetch actual box-score stat + actual minutes from DB
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


def _get_actual_stat_and_min(
    player_name: str, stat: str, game_date: str, db_path
) -> Tuple[Optional[float], Optional[float]]:
    """Return (actual_stat, actual_minutes) for a player on a given date.

    actual_minutes is the minutes played column from player_game_stats.
    Returns (None, None) if player or game not found.
    Returns (actual_stat, None) if stat found but minutes column is NULL.
    """
    col = _STAT_COL_MAP.get(stat.upper())
    if col is None:
        return None, None
    conn = get_conn(db_path)
    name_key = fold_name(player_name)
    row = conn.execute(
        "SELECT player_id FROM players WHERE name_key=?", (name_key,)
    ).fetchone()
    if not row:
        conn.close()
        return None, None
    pid = row["player_id"]
    stat_row = conn.execute(
        f"SELECT pgs.{col}, pgs.min FROM player_game_stats pgs"
        " JOIN games g ON g.game_id = pgs.game_id"
        " WHERE pgs.player_id=? AND g.game_date=?",
        (pid, game_date)
    ).fetchone()
    conn.close()
    if stat_row is None:
        return None, None
    val  = stat_row[col]
    mins = stat_row["min"]
    actual_stat = float(val)  if val  is not None else None
    actual_min  = float(mins) if mins is not None else None
    return actual_stat, actual_min


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


def _get_custom_proj_and_min(
    player_name: str, stat: str, game_date: str, db_path
) -> Tuple[Optional[float], Optional[float]]:
    """Return (custom_proj_stat, proj_min) from the projections table.

    proj_min is the minutes the custom engine projected for this player.
    Returns (None, None) if no projection stored.
    """
    col = _PROJ_COL_MAP.get(stat.upper())
    if col is None:
        return None, None
    conn = get_conn(db_path)
    name_key = fold_name(player_name)
    row = conn.execute(
        "SELECT player_id FROM players WHERE name_key=?", (name_key,)
    ).fetchone()
    if not row:
        conn.close()
        return None, None
    pid = row["player_id"]
    proj_row = conn.execute(
        f"SELECT {col}, proj_min FROM projections WHERE player_id=? AND run_date=?",
        (pid, game_date)
    ).fetchone()
    conn.close()
    if proj_row is None:
        return None, None
    val  = proj_row[col]
    pmin = proj_row["proj_min"]
    proj_stat = float(val)  if val  is not None else None
    proj_min  = float(pmin) if pmin is not None else None
    return proj_stat, proj_min


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


def _get_regen_proj_and_min(
    player_name: str, stat: str, game_date: str, db_path
) -> Tuple[Optional[float], Optional[float]]:
    _regenerate_projections(game_date, db_path)
    name_map = _proj_cache.get(f"{game_date}_map", {})
    p = name_map.get(fold_name(player_name))
    if p is None:
        return None, None
    col = _PROJ_COL_MAP.get(stat.upper())
    proj_stat = p.get(col) if col else None
    proj_min  = p.get("proj_min")
    return (
        float(proj_stat) if proj_stat is not None else None,
        float(proj_min)  if proj_min  is not None else None,
    )


# ---------------------------------------------------------------------------
# Rate-adjusted actual stat (P0 core formula)
# ---------------------------------------------------------------------------

def _rate_adjusted_actual(
    actual_stat: float,
    actual_min: Optional[float],
    proj_min: Optional[float],
) -> Optional[float]:
    """Compute what the player would have produced at their actual per-minute
    rate but in the minutes we projected.

        rate_adj_actual = (actual_stat / actual_min) * proj_min

    Returns None if actual_min <= 0 (DNP) or either input is missing,
    in which case the caller falls back to raw actual.
    """
    if actual_min is None or proj_min is None:
        return None
    if actual_min <= 0:
        return None  # DNP / garbage-time: can't compute a per-minute rate
    return actual_stat / actual_min * proj_min


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
    _proj_cache.clear()  # H26: prevent stale projections across multi-run scenarios
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

    sabersim_errors = []
    custom_errors_raw = []   # |custom_proj - actual_stat|
    custom_errors_adj = []   # |custom_proj - rate_adjusted_actual|  (P0)
    detail_rows = []

    _get_custom = _get_regen_proj_and_min if regen else _get_custom_proj_and_min

    for _, pick in df.iterrows():
        player = str(pick.get("player", ""))
        stat   = str(pick.get("stat", ""))
        date_s = (str(pick["date"].date())
                  if hasattr(pick.get("date"), "date")
                  else str(pick.get("date", "")))
        ss_proj = (float(pick["proj"])
                   if "proj" in pick and pd.notna(pick.get("proj"))
                   else None)

        actual, actual_min = _get_actual_stat_and_min(player, stat, date_s, db_path)
        if actual is None:
            continue
        # CRIT-4: DNP guard — exclude players who did not play (actual_min=0)
        # so they don't inflate raw-error accumulators with full-projection errors
        if actual_min is not None and actual_min == 0:
            continue

        # SaberSim error (raw only — no proj_min available)
        err_ss = None
        if ss_proj is not None:
            err_ss = ss_proj - actual
            sabersim_errors.append(err_ss)

        # Custom projection + projected minutes
        custom_proj, proj_min = _get_custom(player, stat, date_s, db_path)
        err_c_raw = None
        err_c_adj = None
        if custom_proj is not None:
            err_c_raw = custom_proj - actual
            custom_errors_raw.append(err_c_raw)

            # P0: rate-adjusted error
            ra_actual = _rate_adjusted_actual(actual, actual_min, proj_min)
            if ra_actual is not None:
                err_c_adj = custom_proj - ra_actual
                custom_errors_adj.append(err_c_adj)

        if verbose:
            adj_str = f"{err_c_adj:+.2f}" if err_c_adj is not None else "N/A"
            print(f"  {date_s} {player:25s} {stat:4s}"
                  f"  actual={actual:.1f} (min={actual_min or '?'})"
                  f"  proj_min={proj_min or '?'}"
                  f"  ss={ss_proj or 'N/A'!s:5}"
                  f"  custom={custom_proj or 'N/A'!s:5}"
                  f"  err_adj={adj_str}")

        detail_rows.append({
            "date": date_s, "player": player, "stat": stat,
            "actual": actual, "actual_min": actual_min,
            "proj_min": proj_min,
            "sabersim_proj": ss_proj,
            "custom_proj": custom_proj,
            "err_ss": err_ss,
            "err_c_raw": err_c_raw,
            "err_c_adj": err_c_adj,
        })

    n_adj = len(custom_errors_adj)
    n_raw = len(custom_errors_raw)
    n_adj_pct = round(n_adj / n_raw * 100, 1) if n_raw else 0.0

    result = {
        "period": {"since": since, "until": until},
        "sport": sport,
        "stat_filter": stat_filter or "all",
        "n_picks": len(df),
        "n_actuals_found": len(detail_rows),
        # SaberSim: raw only
        "sabersim": {
            "n": len(sabersim_errors),
            "mae":  round(_mae(sabersim_errors),  3),
            "rmse": round(_rmse(sabersim_errors), 3),
            "bias": round(_bias(sabersim_errors), 3),
        },
        # Custom: raw (for backward compat)
        "custom": {
            "n": n_raw,
            "mae":  round(_mae(custom_errors_raw),  3),
            "rmse": round(_rmse(custom_errors_raw), 3),
            "bias": round(_bias(custom_errors_raw), 3),
        },
        # Custom: rate-adjusted (P0 — preferred signal)
        "custom_adj": {
            "n": n_adj,
            "pct_with_minutes": n_adj_pct,
            "mae":  round(_mae(custom_errors_adj),  3),
            "rmse": round(_rmse(custom_errors_adj), 3),
            "bias": round(_bias(custom_errors_adj), 3),
            "note": "error = custom_proj - (actual_stat / actual_min * proj_min)",
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
                breakdown[s] = {"ss": [], "c_raw": [], "c_adj": []}
            if row["err_ss"] is not None:
                breakdown[s]["ss"].append(row["err_ss"])
            if row["err_c_raw"] is not None:
                breakdown[s]["c_raw"].append(row["err_c_raw"])
            if row["err_c_adj"] is not None:
                breakdown[s]["c_adj"].append(row["err_c_adj"])
        result["per_stat"] = {
            s: {
                "sabersim_mae":   round(_mae(v["ss"]),    3),
                "custom_mae_raw": round(_mae(v["c_raw"]), 3),
                "custom_mae_adj": round(_mae(v["c_adj"]), 3),
                "n_ss":  len(v["ss"]),
                "n_raw": len(v["c_raw"]),
                "n_adj": len(v["c_adj"]),
            }
            for s, v in breakdown.items()
        }

    return result


# ---------------------------------------------------------------------------
# P1: Full projections-table sweep (all players, not just pick_log bets)
# ---------------------------------------------------------------------------

def run_backtest_all_projections(
    since, until,
    sport="NBA",
    stat_filter=None,
    db_path=DB_PATH,
    verbose=False,
):
    _proj_cache.clear()  # H26: prevent stale projections across multi-run scenarios
    """Sweep ALL rows in the projections table and compare to actuals.

    P1 implementation: expands from pick_log-filtered n=~40 to all-projections
    n=~500+, giving a truer MAE baseline. No SaberSim comparison (no CSV needed).
    """
    conn = get_conn(db_path)

    # Build query over all projections with a matching game result
    stat_cols = list(_PROJ_COL_MAP.values())  # proj_pts, proj_ast, ...
    stat_cols_sql = ", ".join(f"p.{c}" for c in stat_cols)

    rows = conn.execute(
        f"""
        SELECT
            p.run_date, p.player_name, p.proj_min,
            {stat_cols_sql},
            pgs.pts, pgs.ast, pgs.reb, pgs.fg3m, pgs.blk, pgs.stl,
            pgs.min AS actual_min
        FROM projections p
        JOIN games g   ON g.game_id  = p.game_id
        JOIN player_game_stats pgs
             ON pgs.game_id = g.game_id AND pgs.player_id = p.player_id
        WHERE p.run_date >= ? AND p.run_date <= ?
        ORDER BY p.run_date, p.player_name
        """,
        (str(since), str(until)),
    ).fetchall()
    conn.close()

    log.info("Projections with actuals in range: %d", len(rows))
    if not rows:
        return {"error": "No projections with actuals found in range"}

    # stat name -> (proj_col_index, actual_col_name)
    _STAT_PAIRS = [
        ("PTS",  "proj_pts",  "pts"),
        ("AST",  "proj_ast",  "ast"),
        ("REB",  "proj_reb",  "reb"),
        ("3PM",  "proj_fg3m", "fg3m"),
        ("BLK",  "proj_blk",  "blk"),
        ("STL",  "proj_stl",  "stl"),
    ]

    custom_errors_raw: list = []
    custom_errors_adj: list = []
    detail_rows: list = []
    per_stat: Dict[str, dict] = {}

    for row in rows:
        proj_min  = float(row["proj_min"])  if row["proj_min"]  is not None else None
        actual_min = float(row["actual_min"]) if row["actual_min"] is not None else None

        # CRIT-4: skip DNP players — actual_min=0 inflates raw MAE with full-proj error
        if actual_min is not None and actual_min <= 0:
            continue

        for stat_name, proj_col, actual_col in _STAT_PAIRS:
            if stat_filter and stat_name != stat_filter.upper():
                continue

            proj_val   = row[proj_col]
            actual_val = row[actual_col]
            if proj_val is None or actual_val is None:
                continue

            proj_f   = float(proj_val)
            actual_f = float(actual_val)
            err_raw  = proj_f - actual_f

            ra = _rate_adjusted_actual(actual_f, actual_min, proj_min)
            err_adj = (proj_f - ra) if ra is not None else None

            custom_errors_raw.append(err_raw)
            if err_adj is not None:
                custom_errors_adj.append(err_adj)

            s = per_stat.setdefault(stat_name, {"raw": [], "adj": []})
            s["raw"].append(err_raw)
            if err_adj is not None:
                s["adj"].append(err_adj)

            if verbose:
                adj_str = f"{err_adj:+.2f}" if err_adj is not None else "N/A"
                print(f"  {row['run_date']} {row['player_name']:25s} {stat_name:4s}"
                      f"  actual={actual_f:.1f} (min={actual_min or '?'})"
                      f"  proj_min={proj_min or '?'}"
                      f"  proj={proj_f:.1f}"
                      f"  err_adj={adj_str}")
    n_raw = len(custom_errors_raw)
    n_adj = len(custom_errors_adj)
    n_adj_pct = round(n_adj / n_raw * 100, 1) if n_raw else 0.0

    result = {
        "mode": "all_projections",
        "period": {"since": str(since), "until": str(until)},
        "sport": sport,
        "stat_filter": stat_filter or "all",
        "n_projection_rows": len(rows),
        "n_stat_samples_raw": n_raw,
        "custom": {
            "n": n_raw,
            "mae":  round(_mae(custom_errors_raw),  3),
            "rmse": round(_rmse(custom_errors_raw), 3),
            "bias": round(_bias(custom_errors_raw), 3),
        },
        "custom_adj": {
            "n": n_adj,
            "pct_with_minutes": n_adj_pct,
            "mae":  round(_mae(custom_errors_adj),  3),
            "rmse": round(_rmse(custom_errors_adj), 3),
            "bias": round(_bias(custom_errors_adj), 3),
            "note": "error = custom_proj - (actual_stat / actual_min * proj_min)",
        },
        "per_stat": {
            s: {
                "custom_mae_raw":  round(_mae(v["raw"]),   3),
                "custom_mae_adj":  round(_mae(v["adj"]),   3),
                "custom_bias_raw": round(_bias(v["raw"]),  3),
                "custom_bias_adj": round(_bias(v["adj"]),  3),
                "n_raw": len(v["raw"]),
                "n_adj": len(v["adj"]),
            }
            for s, v in sorted(per_stat.items())
        },
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
    parser.add_argument("--all-projections", dest="all_projections",
                        action="store_true",
                        help="P1: sweep all projections table rows (not pick_log filtered)")
    args = parser.parse_args()

    if args.all_projections:
        result = run_backtest_all_projections(
            since=args.since, until=args.until,
            sport=args.sport, stat_filter=args.stat,
            db_path=args.db, verbose=args.verbose,
        )
        if args.json:
            print(json.dumps(result, indent=2))
            return
        cu  = result["custom"]
        cua = result["custom_adj"]
        print("\n" + "=" * 60)
        print("Backtest (ALL projections): {} | {} | {} -> {}".format(
            result["sport"],
            result.get("stat_filter", "all").upper(),
            result["period"]["since"], result["period"]["until"],
        ))
        print("=" * 60)
        print("Projection rows:   {}".format(result["n_projection_rows"]))
        print("Stat samples:      {}".format(result["n_stat_samples_raw"]))
        print("\nMAE (all projected players, not just bets):")
        print("  Custom    (raw, n={:4d}):  MAE={:.3f}  RMSE={:.3f}  bias={:+.3f}".format(
            cu["n"], cu["mae"], cu["rmse"], cu["bias"]))
        print("  Custom P0 (adj, n={:4d}):  MAE={:.3f}  RMSE={:.3f}  bias={:+.3f}".format(
            cua["n"], cua["mae"], cua["rmse"], cua["bias"]))
        print("    ^ rate-adjusted: error = custom_proj - (actual / actual_min * proj_min)")
        print("    ^ {:.0f}% of samples had minutes data".format(cua["pct_with_minutes"]))
        if "per_stat" in result:
            print("\nPer-stat MAE (raw / adj):")
            for stat, v in sorted(result["per_stat"].items()):
                print("  {:5s}  raw={:.3f}(n={:3d})  adj={:.3f}(n={:3d})"
                      "  bias_raw={:+.3f}  bias_adj={:+.3f}".format(
                    stat,
                    v["custom_mae_raw"], v["n_raw"],
                    v["custom_mae_adj"], v["n_adj"],
                    v["custom_bias_raw"], v["custom_bias_adj"],
                ))
        return

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

    print("\n" + "=" * 60)
    print("Backtest: {} | {} | {} -> {}".format(
        result["sport"],
        result.get("stat_filter", "all").upper(),
        result["period"]["since"], result["period"]["until"],
    ))
    print("=" * 60)
    print("Graded picks:     {}".format(result["n_picks"]))
    print("Actuals found:    {}".format(result["n_actuals_found"]))
    print("Win rate:         {:.1%}".format(result.get("win_rate", float("nan"))))

    clv = result["clv"]
    print("\nCLV (n={}):".format(clv["n_clv"]))
    print("  Mean CLV:       {:+.4f}".format(clv["mean_clv"]))
    if clv["n_clv"]:
        print("  CLV+ rate:      {:.1%}".format(clv["positive_clv_rate"]))

    ss  = result["sabersim"]
    cu  = result["custom"]
    cua = result["custom_adj"]

    print("\nMAE comparison:")
    print("  SaberSim  (raw, n={:3d}):  MAE={:.3f}  RMSE={:.3f}  bias={:+.3f}".format(
        ss["n"], ss["mae"], ss["rmse"], ss["bias"]))
    print("  Custom    (raw, n={:3d}):  MAE={:.3f}  RMSE={:.3f}  bias={:+.3f}".format(
        cu["n"], cu["mae"], cu["rmse"], cu["bias"]))
    print("  Custom P0 (adj, n={:3d}):  MAE={:.3f}  RMSE={:.3f}  bias={:+.3f}".format(
        cua["n"], cua["mae"], cua["rmse"], cua["bias"]))
    print("    ^ rate-adjusted: error = custom_proj - (actual / actual_min * proj_min)")
    print("    ^ {:.0f}% of custom picks had minutes data".format(cua["pct_with_minutes"]))

    if ss["mae"] and cu["mae"] and ss["n"] and cu["n"]:
        delta_raw = ss["mae"] - cu["mae"]
        pct_raw   = delta_raw / ss["mae"] * 100
        print("\n  vs SaberSim (raw):  {:+.3f} ({:+.1f}%)  {}".format(
            delta_raw, pct_raw, "Custom BETTER" if delta_raw > 0 else "Custom WORSE"))
    if ss["mae"] and cua["mae"] and ss["n"] and cua["n"]:
        delta_adj = ss["mae"] - cua["mae"]
        pct_adj   = delta_adj / ss["mae"] * 100
        print("  vs SaberSim (adj):  {:+.3f} ({:+.1f}%)  {}".format(
            delta_adj, pct_adj, "Custom BETTER" if delta_adj > 0 else "Custom WORSE"))

    if "per_stat" in result:
        print("\nPer-stat MAE (ss_raw / custom_raw / custom_adj):")
        for stat, v in sorted(result["per_stat"].items()):
            print("  {:5s}  ss={:.3f}(n={:2d})  raw={:.3f}(n={:2d})  adj={:.3f}(n={:2d})".format(
                stat,
                v["sabersim_mae"], v["n_ss"],
                v["custom_mae_raw"], v["n_raw"],
                v["custom_mae_adj"], v["n_adj"],
            ))


if __name__ == "__main__":
    _main()
