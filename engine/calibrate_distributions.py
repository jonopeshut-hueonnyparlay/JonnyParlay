"""engine/calibrate_distributions.py — Calibrate every stat distribution in the DB.

Runs within-player variance analysis for every numeric stat across all sport tables
in projections.db. Outputs distribution family recommendation (Poisson / NB / Normal)
and calibrated parameters (r for NB, mult+min for Normal) for each stat.

Within-player approach: for each player with enough games, compute mean and variance
of their per-game stat. Pool across players (weighted by game count) to get aggregate
mu, var, and overdispersion index (var/mu). This removes between-player heterogeneity
so the calibrated parameters reflect actual game-to-game unpredictability.

Thresholds for distribution classification:
  var/mu > 1.20  → NB (overdispersed count)
  0.80 ≤ var/mu ≤ 1.20  → Poisson acceptable
  var/mu < 0.80  → underdispersed (bounded count; report only, no NB)
  mu ≥ 5 OR continuous flag  → Normal sigma instead of Poisson/NB

Usage:
    python engine/calibrate_distributions.py                  # all tables
    python engine/calibrate_distributions.py --sport nba      # one sport
    python engine/calibrate_distributions.py --output json    # machine-readable
    python engine/calibrate_distributions.py --min-games 20   # stricter threshold
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR

try:
    from engine_logger import get_logger
    log = get_logger("calibrate_distributions")
except ImportError:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("calibrate_distributions")

DB_PATH: Path = DATA_DIR / "projections.db"

# ---------------------------------------------------------------------------
# Table definitions: which tables to calibrate and how
# ---------------------------------------------------------------------------
# Each entry: (sport_label, table, player_col, filter_clause, stats, min_games)
# filter_clause: applied per-player, per-game to remove garbage rows (DNP, etc.)
# min_games: minimum games per player to include in calibration

TABLES: list[dict[str, Any]] = [
    {
        "sport": "NBA",
        "table": "player_game_stats",
        "player_col": "player_id",
        "filter": "min >= 10",      # exclude DNP / garbage time
        "stats": [
            "pts", "reb", "ast", "fg3m", "stl", "blk", "tov",
            "fgm", "fga", "fg3a", "ftm", "fta", "oreb", "dreb", "pf",
        ],
        "min_games": 15,
        "continuous_stats": set(),           # purely count stats
    },
    {
        "sport": "MLB_P",
        "table": "mlb_pitcher_game_stats",
        "player_col": "player_id",
        "filter": "ip_outs >= 3",   # at least 1 inning pitched
        "stats": [
            "k", "ip_outs", "h", "r", "er", "bb", "hr", "hbp", "bf", "pc", "strikes",
        ],
        "min_games": 8,
        "continuous_stats": {"ip_outs", "pc", "strikes", "bf"},
    },
    {
        "sport": "MLB_B",
        "table": "mlb_batter_game_stats",
        "player_col": "player_id",
        "filter": "ab >= 1",        # actually batted
        "stats": [
            "h", "hr", "rbi", "r", "bb", "k", "tb", "doubles", "triples",
            "sb", "hbp", "sf", "lob", "cs", "ab",
        ],
        "min_games": 20,
        "continuous_stats": {"ab"},
    },
    {
        "sport": "NHL_SK",
        "table": "nhl_skater_game_stats",
        "player_col": "player_id",
        "filter": "toi_secs >= 180",  # 3+ minutes played
        "stats": [
            "sog", "goals", "assists", "points", "hits", "blocked_shots",
            "pp_goals", "giveaways", "takeaways", "pim", "shifts",
        ],
        "min_games": 15,
        "continuous_stats": {"toi_secs", "shifts"},
    },
    {
        "sport": "NHL_G",
        "table": "nhl_goalie_game_stats",
        "player_col": "player_id",
        "filter": "toi_secs >= 1800",  # 30+ minutes (starter-ish)
        "stats": ["sa", "sv", "ga"],
        "min_games": 8,
        "continuous_stats": {"sa", "sv"},   # continuous relative to game context
    },
    {
        "sport": "WNBA",
        "table": "wnba_player_game_stats",
        "player_col": "player_id",
        "filter": "min >= 8",
        "stats": [
            "pts", "reb", "ast", "fg3m", "stl", "blk", "tov",
            "fgm", "fga", "fg3a", "ftm", "fta", "oreb", "dreb", "pf",
        ],
        "min_games": 10,
        "continuous_stats": set(),
    },
]


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 20000")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Within-player calibration
# ---------------------------------------------------------------------------
def calibrate_stat(conn: sqlite3.Connection, cfg: dict, stat: str) -> dict | None:
    """Compute within-player distribution stats for one (table, stat) pair.

    Returns dict with: n_players, n_games, mu, var, var_mu, recommended_dist,
    nb_r, normal_mult, normal_min, note.
    Returns None if insufficient data.
    """
    table = cfg["table"]
    player_col = cfg["player_col"]
    filter_clause = cfg["filter"]
    min_games = cfg["min_games"]
    is_continuous = stat in cfg.get("continuous_stats", set())

    # Within-player aggregation: mean and variance per player
    sql = f"""
        WITH per_player AS (
            SELECT
                {player_col}                                AS pid,
                COUNT(*)                                    AS n,
                AVG(CAST({stat} AS REAL))                   AS mu,
                AVG(CAST({stat} AS REAL) * CAST({stat} AS REAL))
                    - AVG(CAST({stat} AS REAL))
                    * AVG(CAST({stat} AS REAL))             AS var
            FROM {table}
            WHERE {stat} IS NOT NULL
              AND {filter_clause}
            GROUP BY {player_col}
            HAVING COUNT(*) >= {min_games}
               AND AVG(CAST({stat} AS REAL)) > 0.05
        )
        SELECT
            COUNT(*)                          AS n_players,
            SUM(n)                            AS n_games,
            SUM(CAST(n AS REAL) * mu) / SUM(n)  AS weighted_mu,
            SUM(CAST(n AS REAL) * var) / SUM(n) AS weighted_var,
            -- NB r via weighted method of moments
            -- r = sum(n * mu^2) / sum(n * max(var-mu, epsilon))
            SUM(CAST(n AS REAL) * mu * mu)
                / MAX(SUM(CAST(n AS REAL) * MAX(var - mu, 0.001)), 0.001)
                                              AS nb_r_raw,
            -- fraction of players with overdispersion (var > mu)
            SUM(CASE WHEN var > mu THEN 1.0 ELSE 0.0 END) / COUNT(*)
                                              AS overdispersed_frac,
            -- normal CV: weighted mean of sqrt(var)/mu
            SUM(CAST(n AS REAL) * CASE WHEN mu > 0.5 THEN SQRT(MAX(var,0)) / mu ELSE 0 END)
                / NULLIF(SUM(CASE WHEN mu > 0.5 THEN CAST(n AS REAL) ELSE 0 END), 0)
                                              AS normal_cv,
            -- normal min: 10th-percentile std (approximated by 0.5 * avg std)
            0.5 * SUM(CAST(n AS REAL) * SQRT(MAX(var, 0))) / SUM(n)
                                              AS normal_min_raw
        FROM per_player
    """
    try:
        row = conn.execute(sql).fetchone()
    except Exception as exc:
        log.debug("Stat %s.%s skipped: %s", table, stat, exc)
        return None

    if not row or not row["n_players"] or row["n_players"] < 3:
        return None

    n_players = row["n_players"]
    n_games = row["n_games"]
    mu = row["weighted_mu"] or 0.0
    var = max(row["weighted_var"] or 0.0, 0.0)
    var_mu = var / mu if mu > 0.05 else None
    nb_r = max(row["nb_r_raw"] or 0.0, 0.1)
    normal_cv = row["normal_cv"] or 0.0
    normal_min_raw = row["normal_min_raw"] or 0.0

    # Round nb_r to 2 decimal places; cap at 30 (very tight = near Poisson)
    nb_r = min(round(nb_r, 2), 30.0)

    # Sigma floor: use a round number ≥ 0.5 * avg_std, rounded to nearest 0.5
    normal_min = max(round(normal_min_raw * 2) / 2, 0.5)

    # Distribution classification
    note = ""
    if is_continuous or mu >= 8.0:
        # High-mean or continuous → Normal is practical
        dist = "Normal"
        note = "continuous/high-mean → sigma"
    elif var_mu is None or mu < 0.05:
        dist = "insufficient"
        note = "mean too low for reliable classification"
    elif var_mu < 0.80:
        dist = "underdispersed"
        note = f"var/mu={var_mu:.3f} — bounded count (binomial-like); Poisson overstates uncertainty"
    elif var_mu <= 1.20:
        dist = "Poisson"
        note = f"var/mu={var_mu:.3f} — Poisson acceptable"
    else:
        dist = "NB"
        note = f"var/mu={var_mu:.3f} — overdispersed; NB(r={nb_r})"

    return {
        "sport": cfg["sport"],
        "stat": stat,
        "n_players": n_players,
        "n_games": n_games,
        "mu": round(mu, 4),
        "var": round(var, 4),
        "var_mu": round(var_mu, 4) if var_mu is not None else None,
        "overdispersed_frac": round(row["overdispersed_frac"] or 0.0, 3),
        "dist": dist,
        "nb_r": round(nb_r, 2) if dist == "NB" else None,
        "normal_mult": round(normal_cv, 4) if dist in ("Normal",) else None,
        "normal_min": normal_min if dist in ("Normal",) else None,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Main calibration run
# ---------------------------------------------------------------------------
def run_calibration(sports_filter: list[str] | None = None,
                    min_games_override: int | None = None) -> list[dict]:
    results: list[dict] = []

    with get_conn() as conn:
        for cfg in TABLES:
            sport = cfg["sport"]
            if sports_filter and sport.lower() not in [s.lower() for s in sports_filter]:
                continue

            table = cfg["table"]
            if not _table_exists(conn, table):
                log.warning("Table %s does not exist — skipping %s", table, sport)
                continue

            if min_games_override:
                cfg = dict(cfg)
                cfg["min_games"] = min_games_override

            n_rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            log.info("Calibrating %s (%s, %s rows)...", sport, table, f"{n_rows:,}")

            for stat in cfg["stats"]:
                r = calibrate_stat(conn, cfg, stat)
                if r:
                    results.append(r)
                else:
                    log.debug("  %s.%s: no result", sport, stat)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
_CURRENT_PARAMS: dict[tuple[str, str], str] = {
    # (sport_prefix, stat): current deployed description
    ("NBA", "pts"):   "Normal mult=0.35 min=5.0",
    ("NBA", "reb"):   "NB r=10.18",
    ("NBA", "ast"):   "NB r=9.68",
    ("NBA", "fg3m"):  "NB r=9.15",
    ("NBA", "stl"):   "Poisson (assumed)",
    ("NBA", "blk"):   "Poisson (assumed)",
    ("NBA", "tov"):   "Poisson (assumed)",
    ("MLB_P", "k"):   "NB r=5.0 PROVISIONAL",
}


def _fmt_recommended(r: dict) -> str:
    dist = r["dist"]
    if dist == "NB":
        return f"NB r={r['nb_r']}"
    if dist == "Normal":
        mult = r["normal_mult"]
        mn = r["normal_min"]
        mult_s = f"{mult:.3f}" if mult is not None else "?"
        return f"Normal mult={mult_s} min={mn}"
    if dist == "Poisson":
        return "Poisson"
    return dist


def print_report(results: list[dict]) -> None:
    if not results:
        print("No results.")
        return

    # Group by sport
    by_sport: dict[str, list[dict]] = {}
    for r in results:
        by_sport.setdefault(r["sport"], []).append(r)

    for sport, rows in by_sport.items():
        print(f"\n{'='*80}")
        print(f"  {sport}")
        print(f"{'='*80}")
        hdr = f"{'stat':>12}  {'n_pl':>5}  {'n_gm':>7}  {'mu':>7}  {'var/mu':>7}  "
        hdr += f"{'overdisp%':>9}  {'recommended':>22}  current"
        print(hdr)
        print("-" * 110)

        for r in sorted(rows, key=lambda x: -(x["var_mu"] or 0)):
            current = _CURRENT_PARAMS.get((sport, r["stat"]), "uncalibrated")
            recommended = _fmt_recommended(r)
            var_mu_s = f"{r['var_mu']:.3f}" if r["var_mu"] is not None else "  N/A"
            od_pct = f"{r['overdispersed_frac']*100:.0f}%"
            flag = ""
            if r["dist"] == "underdispersed":
                flag = " (**)"
            elif "PROVISIONAL" in current:
                flag = " (*)"

            line = (
                f"{r['stat']:>12}  {r['n_players']:>5}  {r['n_games']:>7,}  "
                f"{r['mu']:>7.3f}  {var_mu_s:>7}  {od_pct:>9}  "
                f"{recommended:>22}  {current}{flag}"
            )
            print(line)

    print()
    print("(*) = currently provisional/assumed")
    print("(**) = underdispersed — Poisson OVERESTIMATES uncertainty")
    print()
    print("Notes:")
    print("  var/mu > 1.20 -> NB (overdispersed); 0.80-1.20 -> Poisson OK; < 0.80 -> underdispersed")
    print("  NB r: within-player method-of-moments. Lower r = more spread. r->inf = Poisson.")
    print("  Normal mult = within-player CV (std/mean); min = sigma floor.")
    print("  All parameters are within-player estimates (between-player variance excluded).")


def save_json(results: list[dict], path: Path) -> None:
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {path}")


def save_csv(results: list[dict], path: Path) -> None:
    import csv
    if not results:
        return
    fieldnames = list(results[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    print(f"Results saved to {path}")


# ---------------------------------------------------------------------------
# Comparison: what has changed vs current deployed params
# ---------------------------------------------------------------------------
def print_changes(results: list[dict]) -> None:
    """Highlight stats where calibrated value differs materially from deployed."""
    print(f"\n{'='*60}")
    print("  ACTIONABLE CHANGES (material difference from deployed)")
    print(f"{'='*60}")

    # Currently deployed NB r values
    deployed_nb_r = {
        ("NBA", "reb"):  10.18,
        ("NBA", "ast"):   9.68,
        ("NBA", "fg3m"):  9.15,
        ("MLB_P", "k"):   5.0,   # provisional
    }
    # Currently deployed Normal params
    deployed_normal = {
        ("NBA", "pts"): (0.35, 5.0),
    }

    changes: list[str] = []

    for r in results:
        key = (r["sport"], r["stat"])
        dist = r["dist"]

        if dist == "NB" and key in deployed_nb_r:
            old_r = deployed_nb_r[key]
            new_r = r["nb_r"]
            if new_r and abs(new_r - old_r) / old_r > 0.10:
                changes.append(
                    f"  {r['sport']:8} {r['stat']:8} NB r: {old_r} -> {new_r}"
                    f"  ({'+' if new_r > old_r else ''}{(new_r-old_r)/old_r*100:.0f}%)"
                )

        elif dist == "Normal" and key in deployed_normal:
            old_mult, old_min = deployed_normal[key]
            new_mult = r["normal_mult"]
            if new_mult and abs(new_mult - old_mult) / old_mult > 0.05:
                changes.append(
                    f"  {r['sport']:8} {r['stat']:8} Normal mult: {old_mult} -> {new_mult:.3f}"
                )

        elif dist == "NB" and key not in deployed_nb_r:
            changes.append(
                f"  {r['sport']:8} {r['stat']:8} NEW: {_fmt_recommended(r)}"
                f"  (currently uncalibrated)"
            )

        elif dist == "underdispersed":
            changes.append(
                f"  {r['sport']:8} {r['stat']:8} UNDERDISPERSED (var/mu={r['var_mu']:.3f})"
                f" — current Poisson overstates uncertainty"
            )

    if changes:
        for c in changes:
            print(c)
    else:
        print("  No material changes detected.")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate every stat distribution across all sport DB tables"
    )
    parser.add_argument(
        "--sport", nargs="+",
        help="Filter to specific sports (NBA, MLB_P, MLB_B, NHL_SK, NHL_G, WNBA)",
    )
    parser.add_argument(
        "--output", choices=["table", "json", "csv"], default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--min-games", type=int,
        help="Override minimum games per player threshold",
    )
    parser.add_argument(
        "--save", type=Path,
        help="Save results to file (path; format inferred from extension)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    results = run_calibration(
        sports_filter=args.sport,
        min_games_override=args.min_games,
    )

    if args.output == "json":
        print(json.dumps(results, indent=2))
    elif args.output == "csv":
        import csv, io
        if results:
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
            print(buf.getvalue())
    else:
        print_report(results)
        print_changes(results)

    if args.save:
        p = args.save
        if p.suffix == ".json":
            save_json(results, p)
        elif p.suffix == ".csv":
            save_csv(results, p)
        else:
            save_json(results, p.with_suffix(".json"))


if __name__ == "__main__":
    main()
