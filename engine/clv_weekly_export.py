#!/usr/bin/env python3
"""clv_weekly_export.py — weekly CLV ledger CSV export (audit S4k-X).

Writes one CSV for a completed Mon–Sun week: every graded pick with its closing line
and CLV, sorted, plus a one-line console summary (coverage, avg CLV, beat-close rate).
An ops / record-keeping artifact.

Reuse, not forks: pick_log is read through the canonical locked reader
(``pick_log_io.load_rows``, audit H-8) and the week window + CLV summary come from
``weekly_recap`` (``week_range`` / ``week_range_containing`` / ``compute_clv_summary``).
Read-only on the ledger — only the export file is written.

Usage:
    python engine/clv_weekly_export.py                    # last completed Mon–Sun week
    python engine/clv_weekly_export.py --week 2026-06-15  # week containing that date
    python engine/clv_weekly_export.py --out path.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR, PICK_LOG_PATH  # noqa: E402
from pick_log_io import load_rows  # noqa: E402
from weekly_recap import compute_clv_summary, week_range, week_range_containing  # noqa: E402

# CLV-relevant ledger columns (a stable subset of the canonical pick_log schema).
LEDGER_COLS = [
    "date", "sport", "player", "team", "stat", "line", "direction",
    "book", "odds", "closing_odds", "clv", "result", "tier", "size",
]

# CLV is a single-side concept: SGPs/parlays/daily-lay/longshots have no per-leg
# closing line, so they carry no CLV and are excluded from the CLV population
# (matches clv_report.load_all_picks — keeps coverage/avg-CLV meaningful).
EXCLUDE_RUN_TYPES = ["daily_lay", "sgp", "longshot"]
EXCLUDE_STATS = ["PARLAY"]


def write_ledger_csv(rows: list[dict], out_path) -> int:
    """Write the CLV ledger rows to ``out_path`` (sorted by date/sport/player).

    Returns the number of rows written. Unknown columns are dropped
    (``extrasaction='ignore'``) so the export contract stays fixed regardless of
    pick_log schema growth.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        rows,
        key=lambda r: (r.get("date", ""), r.get("sport", ""), str(r.get("player", ""))),
    )
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLS, extrasaction="ignore")
        writer.writeheader()
        for r in ordered:
            writer.writerow({c: r.get(c, "") for c in LEDGER_COLS})
    return len(ordered)


def export_week(monday: str, sunday: str, out_path, log_paths=None) -> tuple[int, dict]:
    """Load graded picks in [monday, sunday], write the ledger CSV, return (n, summary)."""
    paths = log_paths or [PICK_LOG_PATH]
    rows = load_rows(paths, date_range=(monday, sunday), graded_only=True,
                     exclude_run_types=EXCLUDE_RUN_TYPES, exclude_stats=EXCLUDE_STATS)
    n = write_ledger_csv(rows, out_path)
    return n, compute_clv_summary(rows)


def main():
    ap = argparse.ArgumentParser(description="Weekly CLV ledger CSV export")
    ap.add_argument("--week", help="any date YYYY-MM-DD in the target week "
                                   "(default: last completed Mon–Sun week)")
    ap.add_argument("--out", help="output CSV path "
                                  "(default: data/clv_exports/clv_week_<mon>_to_<sun>.csv)")
    args = ap.parse_args()

    if args.week:
        monday, sunday = week_range_containing(date.fromisoformat(args.week))
    else:
        monday, sunday = week_range()
    out = Path(args.out) if args.out else (
        DATA_DIR / "clv_exports" / f"clv_week_{monday}_to_{sunday}.csv")

    n, s = export_week(monday, sunday, out)
    avg = f"{s['avg_clv'] * 100:.2f}pp" if s["avg_clv"] is not None else "n/a"
    beat = f"{s['beat_close_pct']:.1f}%" if s["beat_close_pct"] is not None else "n/a"
    print(f"CLV weekly export {monday} -> {sunday}: {n} graded picks -> {out}")
    print(f"  CLV captured {s['captured']}/{s['total']} ({s['coverage_pct']:.1f}%) | "
          f"avg CLV {avg} | beat close {beat}")


if __name__ == "__main__":
    main()
