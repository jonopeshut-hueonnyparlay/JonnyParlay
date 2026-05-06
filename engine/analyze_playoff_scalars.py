"""H2 — Playoff minutes scalar refit analysis.

Pulls every playoff player-game across 2023-24, 2024-25, 2025-26 from the DB,
computes the baseline `project_minutes` projection (pre-PLAYOFF_MINUTES_SCALAR),
and reports the empirically-fitted scalar per role tier (and per season + round
when sample allows).

This is a one-shot analysis script — does not modify production code or DB.

Output:
  - data/diagnostics/playoff_baseline_data.csv  (one row per matched player-game)
  - docs/research/playoff_scalar_refit.md       (markdown report with recommended values)

Usage:
    python engine/analyze_playoff_scalars.py
"""
from __future__ import annotations

import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from nba_projector import (
    classify_role, project_minutes,
    PLAYOFF_MINUTES_SCALAR,
)
from paths import DATA_DIR, project_path
from projections_db import (
    DB_PATH, get_conn, get_player_recent_games, get_player_b2b_context,
)

log = logging.getLogger("analyze_playoff_scalars")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Round bucketing — derive from playoff date offset within each season.
# Playoffs are ~2 months long.  Days 0-30 ≈ R1+R2 (early); days 30+ ≈ CF+Finals (deep).
# Lazy heuristic when we don't have explicit round metadata.
_DEEP_ROUND_DAY_THRESHOLD = 30


def _playoff_start_date(season: str, db_path: Path) -> str:
    """Earliest playoff game date for the given season."""
    con = get_conn(db_path)
    try:
        row = con.execute(
            "SELECT MIN(game_date) AS d FROM games "
            "WHERE season=? AND season_type='Playoffs'",
            (season,)
        ).fetchone()
    finally:
        con.close()
    return row["d"] if row else None


def _round_bucket(game_date: str, playoff_start: str) -> str:
    """Bucket a playoff game date into 'early' (R1+R2) or 'deep' (CF+Finals)."""
    if not playoff_start:
        return "unknown"
    from datetime import date
    d_game = date.fromisoformat(game_date)
    d_start = date.fromisoformat(playoff_start)
    days = (d_game - d_start).days
    return "deep" if days >= _DEEP_ROUND_DAY_THRESHOLD else "early"


def _iter_playoff_player_games(db_path: Path):
    """Yield (player_id, game_id, game_date, season, team_id, position, actual_min,
    is_starter) for every playoff player-game with min >= 5 across all seasons.
    """
    con = get_conn(db_path)
    try:
        rows = con.execute("""
            SELECT
                pgs.player_id,
                pgs.game_id,
                g.game_date,
                g.season,
                pgs.team_id,
                p.position,
                pgs.min      AS actual_min,
                pgs.starter_flag
            FROM player_game_stats pgs
            JOIN games   g ON g.game_id = pgs.game_id
            JOIN players p ON p.player_id = pgs.player_id
            WHERE g.season_type = 'Playoffs'
              AND pgs.min >= 5
            ORDER BY g.season, g.game_date
        """).fetchall()
    finally:
        con.close()
    for r in rows:
        yield dict(r)


def main(db_path: Path = DB_PATH) -> None:
    log.info("H2 playoff scalar refit — loading playoff player-games...")
    rows = list(_iter_playoff_player_games(db_path))
    log.info("  loaded %d player-games (min >= 5) across all playoff seasons", len(rows))

    # Cache playoff start dates per season for round bucketing
    seasons = sorted({r["season"] for r in rows})
    playoff_starts = {s: _playoff_start_date(s, db_path) for s in seasons}
    for s, d in playoff_starts.items():
        log.info("  %s playoffs start: %s", s, d)

    # Compute baseline projection per row
    out_rows = []
    n_skipped = 0
    n_cold_start = 0
    for i, r in enumerate(rows, 1):
        pid       = r["player_id"]
        game_date = r["game_date"]
        season    = r["season"]
        actual_min = float(r["actual_min"])
        position   = r["position"] or "G"

        # Pull last 30 games BEFORE this playoff game; restrict to current season
        df = get_player_recent_games(
            pid, before_date=game_date, n_games=30,
            season_filter=season, db_path=db_path,
        )
        if df.empty or len(df) < 5:
            # Insufficient history for stable role classification
            n_skipped += 1
            continue

        role = classify_role(df)
        if role == "cold_start":
            # Skip cold_start in this analysis — scalar fit needs stable role
            # signal, and cold_start has its own sub-type cap logic.
            n_cold_start += 1
            continue

        b2b = get_player_b2b_context(pid, game_date, db_path)
        # Baseline projection — pre-PLAYOFF_MINUTES_SCALAR.  No spread, no
        # injury override, no redistribution bump.  This is what
        # project_player() would multiply by PLAYOFF_MINUTES_SCALAR[role].
        baseline_min = project_minutes(
            role=role, df=df, b2b=b2b,
            spread=None, injury_minutes_override=None,
            minutes_prior_override=None,
        )
        if baseline_min < 1.0:
            n_skipped += 1
            continue

        round_bucket = _round_bucket(game_date, playoff_starts.get(season))

        out_rows.append({
            "season":     season,
            "game_date":  game_date,
            "round":      round_bucket,
            "player_id":  pid,
            "role":       role,
            "baseline_min": round(baseline_min, 3),
            "actual_min":   round(actual_min, 3),
            "ratio":      round(actual_min / baseline_min, 4),
            "is_starter": int(r["starter_flag"] or 0),
        })

        if i % 500 == 0:
            log.info("  ...%d / %d processed", i, len(rows))

    log.info("Computed baseline for %d rows (skipped: %d insufficient history, "
             "%d cold_start)", len(out_rows), n_skipped, n_cold_start)

    # Write CSV
    out_csv = DATA_DIR / "diagnostics" / "playoff_baseline_data.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    log.info("Wrote %s", out_csv)

    # ------------------------------------------------------------------
    # Aggregate scalars: by role, by season×role, by round×role
    # ------------------------------------------------------------------
    def _summarize(group_key_fn, label: str) -> list[tuple]:
        buckets = defaultdict(list)
        for r in out_rows:
            buckets[group_key_fn(r)].append(r)
        results = []
        for key, items in buckets.items():
            n = len(items)
            avg_actual = mean(x["actual_min"] for x in items)
            avg_base   = mean(x["baseline_min"] for x in items)
            scalar     = avg_actual / avg_base if avg_base > 0 else 0.0
            # Per-row ratio mean (less sensitive to outlier games)
            avg_ratio  = mean(x["ratio"] for x in items)
            results.append((key, n, avg_actual, avg_base, scalar, avg_ratio))
        results.sort(key=lambda x: (str(x[0])))
        return results

    # ------------------------------------------------------------------
    # Build markdown report
    # ------------------------------------------------------------------
    report_lines = []
    report_lines.append("# H2 — Playoff Minutes Scalar Refit")
    report_lines.append("")
    report_lines.append(f"**Analysis date**: 2026-05-06")
    report_lines.append(f"**Sample**: {len(out_rows)} playoff player-games "
                        f"(min ≥ 5) across {', '.join(seasons)}")
    report_lines.append(f"**Method**: For each row, compute baseline_min via "
                        f"`project_minutes()` pre-PLAYOFF_MINUTES_SCALAR. "
                        f"Fitted scalar = mean(actual_min) / mean(baseline_min) per cell.")
    report_lines.append("")
    report_lines.append("## Current PLAYOFF_MINUTES_SCALAR (pre-refit)")
    report_lines.append("")
    report_lines.append("| Role | Current scalar |")
    report_lines.append("|------|---:|")
    for role, val in sorted(PLAYOFF_MINUTES_SCALAR.items()):
        report_lines.append(f"| {role} | {val:.3f} |")
    report_lines.append("")

    # Pooled-by-role
    report_lines.append("## Refit by role tier (all seasons pooled)")
    report_lines.append("")
    report_lines.append("| Role | n | mean(actual) | mean(baseline) | **fitted scalar** | mean(ratio) | current | Δ |")
    report_lines.append("|------|--:|-------------:|---------------:|-----------------:|------------:|--------:|---:|")
    role_results = _summarize(lambda r: r["role"], "role")
    for role, n, ma, mb, sc, mr in role_results:
        cur = PLAYOFF_MINUTES_SCALAR.get(role, 1.0)
        delta = sc - cur
        report_lines.append(
            f"| {role} | {n} | {ma:.2f} | {mb:.2f} | **{sc:.3f}** | {mr:.3f} | {cur:.3f} | {delta:+.3f} |"
        )
    report_lines.append("")

    # Per-season per-role
    report_lines.append("## Refit by season × role")
    report_lines.append("")
    report_lines.append("| Season | Role | n | mean(actual) | mean(baseline) | fitted scalar |")
    report_lines.append("|--------|------|--:|-------------:|---------------:|---:|")
    sxrole = _summarize(lambda r: (r["season"], r["role"]), "season×role")
    for (season, role), n, ma, mb, sc, mr in sxrole:
        report_lines.append(f"| {season} | {role} | {n} | {ma:.2f} | {mb:.2f} | {sc:.3f} |")
    report_lines.append("")

    # Per-round per-role
    report_lines.append("## Refit by round × role")
    report_lines.append("")
    report_lines.append("'early' = days 0-29 within each season's playoff window (R1 + R2). "
                        "'deep' = days 30+ (CF + Finals).")
    report_lines.append("")
    report_lines.append("| Round | Role | n | mean(actual) | mean(baseline) | fitted scalar |")
    report_lines.append("|-------|------|--:|-------------:|---------------:|---:|")
    rxrole = _summarize(lambda r: (r["round"], r["role"]), "round×role")
    for (rnd, role), n, ma, mb, sc, mr in rxrole:
        report_lines.append(f"| {rnd} | {role} | {n} | {ma:.2f} | {mb:.2f} | {sc:.3f} |")
    report_lines.append("")

    # Recommendation
    report_lines.append("## Recommendation")
    report_lines.append("")
    report_lines.append("See pooled `fitted scalar` column for the proposed update. "
                        "Use round-stratified values only if cell sizes per "
                        "(round × role) ≥ 100 and per-cell values diverge from "
                        "pooled by ≥ 0.05; otherwise prefer pooled scalars to "
                        "avoid small-sample noise.")
    report_lines.append("")
    report_lines.append("Raw data: `data/diagnostics/playoff_baseline_data.csv`")

    out_md = project_path("docs", "research", "playoff_scalar_refit.md")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    # Explicit UTF-8 — Windows default cp1252 chokes on '≥', 'Δ' etc.
    out_md.write_text("\n".join(report_lines), encoding="utf-8")
    log.info("Wrote %s", out_md)

    print()
    print("=" * 70)
    print("Pooled-by-role fitted scalars vs current:")
    print("=" * 70)
    print(f"{'role':<12} {'n':>5} {'fitted':>8} {'current':>8} {'Δ':>8}")
    for role, n, ma, mb, sc, mr in role_results:
        cur = PLAYOFF_MINUTES_SCALAR.get(role, 1.0)
        print(f"{role:<12} {n:>5} {sc:>8.3f} {cur:>8.3f} {sc-cur:+8.3f}")
    print()


if __name__ == "__main__":
    main()
