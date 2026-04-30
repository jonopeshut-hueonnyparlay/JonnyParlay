"""Diagnostic bucket slice of the NBA projector MAE.

READ-ONLY. Re-runs the same window as ``backtest_projections.py`` and
breaks the MAE / bias down by four buckets:

    1. starter_flag               (proxy: actual minutes >= 20)
    2. projected_minutes_bucket   (<15, 15-20, 20-25, 25-30, 30-35, 35+)
    3. usage_tier_on_team         (top3, 4-6, 7+ by projected minutes)
    4. position                   (G / F / C, collapsed)

Answers one question and one question only: where is the PTS
under-projection concentrated on the full-sample failure?

This script does NOT:
- modify projection / minutes code
- modify backtest_projections.py
- write to projections.db (read-only connection usage)
- push any "fix"

Outputs:
- ``{stem}.csv`` -- per-row projected/actual + err columns + bucket cols
- ``{stem}.txt`` -- human-readable report with four bucket tables

CLI:
    python engine/backtest_slice.py \\
        --start 2026-03-29 --end 2026-04-12 \\
        --out slice_results_2026-04-22
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

try:
    from engine import backtest_projections as _bt      # type: ignore
    from engine import projections_db as _pdb           # type: ignore
    from engine.name_utils import fold_name             # type: ignore
except ImportError:  # pragma: no cover -- script mode
    import backtest_projections as _bt                  # type: ignore
    import projections_db as _pdb                       # type: ignore
    from name_utils import fold_name                    # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bucket definitions
# ---------------------------------------------------------------------------

#: Ordered projected-minutes buckets. Used both for labelling and for
#: optional fixed-order display.
MINUTES_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("<15",    float("-inf"), 15.0),
    ("15-20",  15.0,          20.0),
    ("20-25",  20.0,          25.0),
    ("25-30",  25.0,          30.0),
    ("30-35",  30.0,          35.0),
    ("35+",    35.0,          float("inf")),
)

STARTER_MIN_THRESHOLD: float = 20.0   # proxy only; no native starter flag
USAGE_TIER_TOP: int = 3
USAGE_TIER_MID_MAX: int = 6


def _bucket_minutes(m: float) -> str:
    if m is None or (isinstance(m, float) and math.isnan(m)):
        return "unknown"
    for label, lo, hi in MINUTES_BUCKETS:
        if lo <= m < hi:
            return label
    return "unknown"


def _collapse_position(pos: str) -> str:
    """Collapse raw position strings to G/F/C.

    Handles dual-position tokens like ``"G-F"`` or ``"F/C"`` by taking the
    primary (leftmost) token. Returns ``"UNK"`` if the field is empty or
    not one of the standard five tokens.
    """
    if not pos:
        return "UNK"
    p = pos.upper().strip()
    primary = p.split("-")[0].split("/")[0].strip()
    if primary in ("G", "PG", "SG"):
        return "G"
    if primary in ("F", "SF", "PF"):
        return "F"
    if primary == "C":
        return "C"
    return "UNK"


# ---------------------------------------------------------------------------
# Player metadata (team, position) from player_index
# ---------------------------------------------------------------------------

def _load_player_index(conn: sqlite3.Connection) -> dict[str, dict]:
    """Return ``{folded_name: {"team": str, "position": str}}``.

    ``player_index`` is the only place team + position live in the DB --
    ``player_game_logs`` doesn't store either. This is the player's
    *current* team, not the team they were on for a given historical game,
    so a mid-season traded player will bucket under their current team.
    Flagged in the report's derivation notes.
    """
    out: dict[str, dict] = {}
    try:
        cur = conn.execute("SELECT fold_name, team, position FROM player_index")
    except sqlite3.OperationalError:
        logger.warning("player_index table missing -- position/team buckets will be UNK/no_team")
        return out
    for r in cur.fetchall():
        # sqlite3.Row or tuple -- access by index to be tolerant
        fn = r[0] or ""
        team = (r[1] or "") if len(r) > 1 else ""
        pos = (r[2] or "") if len(r) > 2 else ""
        if fn:
            out[fn] = {"team": team, "position": pos}
    return out


# ---------------------------------------------------------------------------
# Row building
# ---------------------------------------------------------------------------

def build_slice_rows(
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
    min_minutes: float,
) -> list[dict]:
    """Run the same backtest loop and annotate each projected row with
    bucket columns.

    Skipped rows (projector refused for insufficient games) are dropped
    here -- they have no projection, so there's nothing to slice.
    """
    idx = _load_player_index(conn)
    logger.info("player_index loaded: %d entries", len(idx))

    bt_rows = _bt.backtest(
        conn,
        start_date=start_date,
        end_date=end_date,
        min_minutes=min_minutes,
    )

    out: list[dict] = []
    for r in bt_rows:
        if not r.projected:
            continue
        folded = fold_name(r.player_name)
        meta = idx.get(folded, {"team": "", "position": ""})
        pos_raw = meta.get("position") or ""
        team = meta.get("team") or ""
        pos_collapsed = _collapse_position(pos_raw)
        starter = "starter" if r.minutes_actual >= STARTER_MIN_THRESHOLD else "bench"
        min_bucket = _bucket_minutes(r.minutes_proj)

        out.append({
            "game_date":     r.game_date,
            "player_name":   r.player_name,
            "opponent":      r.opponent,
            "team":          team,
            "position_raw":  pos_raw,
            "position":      pos_collapsed,
            "starter_flag": starter,
            "min_bucket":    min_bucket,
            "usage_tier":    "",   # filled in below
            "min_actual":    r.minutes_actual,
            "min_proj":      r.minutes_proj,
            "min_err":       r.minutes_proj - r.minutes_actual,
            "pts_actual":    r.pts_actual,
            "pts_proj":      r.pts_proj,
            "pts_err":       r.err("pts"),
            "reb_actual":    r.reb_actual,
            "reb_proj":      r.reb_proj,
            "reb_err":       r.err("reb"),
            "ast_actual":    r.ast_actual,
            "ast_proj":      r.ast_proj,
            "ast_err":       r.err("ast"),
            "tpm_actual":    r.tpm_actual,
            "tpm_proj":      r.tpm_proj,
            "tpm_err":       r.err("tpm"),
        })

    # ---- Usage tier: rank within (team, game_date) by projected minutes ----
    by_tg: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, row in enumerate(out):
        by_tg[(row["team"], row["game_date"])].append(i)
    for (team, _gd), indices in by_tg.items():
        indices.sort(key=lambda i: out[i]["min_proj"], reverse=True)
        for rank, i in enumerate(indices, start=1):
            if not team:
                out[i]["usage_tier"] = "no_team"
            elif rank <= USAGE_TIER_TOP:
                out[i]["usage_tier"] = "top3"
            elif rank <= USAGE_TIER_MID_MAX:
                out[i]["usage_tier"] = "4-6"
            else:
                out[i]["usage_tier"] = "7+"
    return out


# ---------------------------------------------------------------------------
# Aggregation / reporting
# ---------------------------------------------------------------------------

def _aggregate(rows: list[dict], bucket_col: str) -> list[dict]:
    """Group rows by ``bucket_col``, compute per-stat MAE / bias summary.

    Returns one dict per bucket, sorted by sample size descending.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r[bucket_col]].append(r)

    out: list[dict] = []
    for bucket, grp in groups.items():
        n = len(grp)
        if not n:
            continue
        out.append({
            "bucket":   bucket,
            "n":        n,
            "pts_mae":  sum(abs(r["pts_err"]) for r in grp) / n,
            "pts_bias": sum(r["pts_err"] for r in grp) / n,
            "min_bias": sum(r["min_err"] for r in grp) / n,
            "reb_bias": sum(r["reb_err"] for r in grp) / n,
            "ast_bias": sum(r["ast_err"] for r in grp) / n,
        })
    out.sort(key=lambda e: e["n"], reverse=True)
    return out


def _format_table(title: str, table: list[dict]) -> str:
    lines = [title, "-" * len(title)]
    header = (
        f"{'bucket':<20} {'n':>5} {'PTS_MAE':>8} "
        f"{'PTS_bias':>9} {'MIN_bias':>9} {'REB_bias':>9} {'AST_bias':>9}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    if not table:
        lines.append("  (no rows)")
        return "\n".join(lines)
    for row in table:
        lines.append(
            f"{str(row['bucket'])[:20]:<20} {row['n']:>5} "
            f"{row['pts_mae']:>8.3f} {row['pts_bias']:>+9.3f} "
            f"{row['min_bias']:>+9.3f} {row['reb_bias']:>+9.3f} "
            f"{row['ast_bias']:>+9.3f}"
        )
    return "\n".join(lines)


def build_report(rows: list[dict]) -> str:
    n = len(rows)
    parts: list[str] = []
    parts.append(f"Slice diagnostic -- n={n} projected rows")
    parts.append("")
    parts.append("Derivations:")
    parts.append(
        f"  starter_flag : actual minutes >= {STARTER_MIN_THRESHOLD:.0f} -> "
        "'starter' else 'bench' (PROXY -- no native starter flag in DB; "
        "uses post-hoc actual minutes)"
    )
    parts.append(
        "  position     : player_index.position (native, current team); "
        "collapsed G/PG/SG -> G, F/SF/PF -> F, C -> C; UNK if missing"
    )
    parts.append(
        "  team         : player_index.team (native, CURRENT team, not "
        "game-time team -- traded players will misbucket). Empty team -> "
        "usage_tier='no_team'"
    )
    parts.append(
        "  usage_tier   : rank within (team, game_date) by PROJECTED "
        "minutes desc -> top3 / 4-6 / 7+ (PROXY -- no projected_usage% "
        "available)"
    )
    parts.append("")
    parts.append(_format_table("1. starter_flag", _aggregate(rows, "starter_flag")))
    parts.append("")
    parts.append(_format_table(
        "2. projected_minutes_bucket", _aggregate(rows, "min_bucket")
    ))
    parts.append("")
    parts.append(_format_table(
        "3. usage_tier_on_team", _aggregate(rows, "usage_tier")
    ))
    parts.append("")
    parts.append(_format_table("4. position", _aggregate(rows, "position")))
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict], path: Path) -> None:
    """Write per-row slice table. Floats are formatted to 3 decimals."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            outrow = {}
            for k, v in r.items():
                if isinstance(v, float):
                    if math.isnan(v):
                        outrow[k] = ""
                    else:
                        outrow[k] = f"{v:.3f}"
                else:
                    outrow[k] = v
            writer.writerow(outrow)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Diagnostic bucket slice of the NBA projector MAE.",
    )
    p.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--end",   required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument(
        "--min-minutes", type=float, default=_bt.DEFAULT_MIN_MINUTES,
        help=f"Exclude games under N minutes "
             f"(default {_bt.DEFAULT_MIN_MINUTES}, matches backtest_projections.py)",
    )
    p.add_argument(
        "--out", default="slice_results",
        help="Output file stem (no extension). Writes {stem}.csv and {stem}.txt.",
    )
    p.add_argument(
        "--db", default=None,
        help="Override DB path (defaults to data/projections.db).",
    )
    p.add_argument("-v", "--verbose", action="count", default=0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    level = logging.WARNING
    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose >= 1:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    conn = _pdb.get_connection(args.db)
    try:
        rows = build_slice_rows(
            conn,
            start_date=args.start,
            end_date=args.end,
            min_minutes=args.min_minutes,
        )
    finally:
        conn.close()

    stem = Path(args.out)
    csv_path = stem.with_suffix(".csv")
    txt_path = stem.with_suffix(".txt")

    write_csv(rows, csv_path)
    report = build_report(rows)
    txt_path.write_text(report, encoding="utf-8")

    # ---- Overall sanity print so the caller can confirm the slice
    # reproduces the original backtest aggregate MAE / bias. ----
    n = len(rows)
    print()
    print(f"Window : {args.start} .. {args.end}")
    print(f"Rows   : {n} projected")
    print()
    if n:
        for stat in ("pts", "reb", "ast", "tpm"):
            errs = [r[f"{stat}_err"] for r in rows]
            mae = sum(abs(e) for e in errs) / n
            bias = sum(errs) / n
            print(f"OVERALL {stat.upper():3s}  n={n}  MAE={mae:.3f}  bias={bias:+.3f}")
        min_errs = [r["min_err"] for r in rows]
        print(
            f"OVERALL MIN  n={n}  "
            f"MAE={sum(abs(e) for e in min_errs)/n:.3f}  "
            f"bias={sum(min_errs)/n:+.3f}"
        )

    print()
    print(f"Wrote {csv_path}")
    print(f"Wrote {txt_path}")
    print()
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
