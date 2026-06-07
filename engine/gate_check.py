"""
gate_check.py — print current counts for all open gates in one shot.

Usage:
    python engine/gate_check.py
"""

import csv
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution — works whether run from project root or engine/
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

PICK_LOG        = DATA / "pick_log.csv"
PICK_LOG_CUSTOM = DATA / "pick_log_custom.csv"
PICK_LOG_WNBA   = DATA / "pick_log_wnba.csv"

WNBA_DAMPENER_DATE = "2026-06-03"

COMBO_STATS = {"RA", "PRA", "PR", "PA"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _nonempty(val: str | None) -> bool:
    return bool(val and val.strip())


# ---------------------------------------------------------------------------
# Gate counters
# ---------------------------------------------------------------------------

def count_h3_platt(rows: list[dict]) -> int:
    """Graded rows with over_p_raw populated (any sport, props only)."""
    return sum(
        1 for r in rows
        if _nonempty(r.get("over_p_raw")) and _nonempty(r.get("result"))
    )


def count_mlb_platt(rows: list[dict]) -> int:
    """MLB graded rows with over_p_raw populated."""
    return sum(
        1 for r in rows
        if r.get("sport", "").strip() == "MLB"
        and _nonempty(r.get("over_p_raw"))
        and _nonempty(r.get("result"))
    )


def count_sgp_platt(rows: list[dict]) -> int:
    """Scored (graded) SGP slips."""
    return sum(
        1 for r in rows
        if r.get("run_type", "").strip() == "sgp"
        and _nonempty(r.get("result"))
    )


def count_combo_platt(rows: list[dict]) -> int:
    """Scored combo picks (stat in RA/PRA/PR/PA)."""
    return sum(
        1 for r in rows
        if r.get("stat", "").strip().upper() in COMBO_STATS
        and _nonempty(r.get("result"))
    )


def count_edgemodel_clv(rows: list[dict]) -> int:
    """pick_log_custom.csv rows with a non-empty clv value."""
    return sum(1 for r in rows if _nonempty(r.get("clv")))


def count_wnba_graded(rows: list[dict]) -> int:
    """Graded WNBA picks on or after dampener date."""
    return sum(
        1 for r in rows
        if r.get("date", "") >= WNBA_DAMPENER_DATE
        and _nonempty(r.get("result"))
    )


# ---------------------------------------------------------------------------
# Gate definitions
# ---------------------------------------------------------------------------

GATES = [
    # (label, counter_fn, target, note)
    ("H3 Platt refit",     count_h3_platt,      100, "graded over_p_raw rows (all sports)"),
    ("MLB Platt refit",    count_mlb_platt,      100, "graded MLB over_p_raw rows"),
    ("EdgeModel CLV",      count_edgemodel_clv,  100, "CLV rows in pick_log_custom.csv"),
    ("WNBA go-live",       count_wnba_graded,    100, "graded picks post-2026-06-03"),
    ("SGP Platt calib",    count_sgp_platt,      100, "scored SGP slips"),
    ("Combo Platt calib",  count_combo_platt,    100, "scored RA/PRA/PR/PA picks"),
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _status(count: int, target: int) -> str:
    pct = count / target * 100
    if count >= target:
        return "*** REACHED — ready to act ***"
    bar = int(pct / 5)  # 20-char wide bar
    return f"[{'#' * bar}{'.' * (20 - bar)}] {pct:5.1f}%"


def main() -> None:
    main_rows   = _read_csv(PICK_LOG)
    custom_rows = _read_csv(PICK_LOG_CUSTOM)
    wnba_rows   = _read_csv(PICK_LOG_WNBA)

    # Route the right row-set to each gate counter
    row_map = {
        count_h3_platt:     main_rows,
        count_mlb_platt:    main_rows,
        count_sgp_platt:    main_rows,
        count_combo_platt:  main_rows,
        count_edgemodel_clv: custom_rows,
        count_wnba_graded:  wnba_rows,
    }

    results = []
    for label, fn, target, note in GATES:
        rows  = row_map[fn]
        count = fn(rows)
        results.append((label, count, target, note))

    # Column widths
    w_label  = max(len(r[0]) for r in results) + 2
    w_count  = 7
    w_target = 7
    w_status = 30

    header = (
        f"{'Gate':<{w_label}} {'Count':>{w_count}} {'Target':>{w_target}}  "
        f"{'Status':<{w_status}}  Note"
    )
    sep = "-" * (len(header) + 10)

    print()
    print("  JonnyParlay -- Open Gate Status")
    print(f"  {sep}")
    print(f"  {header}")
    print(f"  {sep}")

    for label, count, target, note in results:
        status = _status(count, target)
        reached = count >= target
        marker = "*" if reached else " "
        print(
            f"  {marker} {label:<{w_label}} {count:>{w_count}} {target:>{w_target}}  "
            f"{status:<{w_status}}  {note}"
        )

    print(f"  {sep}")
    open_count = sum(1 for _, c, t, _ in results if c >= t)
    total = len(results)
    print(f"  {open_count}/{total} gates reached\n")


if __name__ == "__main__":
    main()
