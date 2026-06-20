"""
gate_check.py — print current counts for all open gates in one shot.

Usage:
    python engine/gate_check.py
"""

import csv
import os
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution — works whether run from project root or engine/
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

PICK_LOG        = DATA / "pick_log.csv"
PICK_LOG_CUSTOM = DATA / "pick_log_custom.csv"
PICK_LOG_CALIBRATION = DATA / "pick_log_calibration.csv"

COMBO_STATS = {"RA", "PRA", "PR", "PA"}

# Calibration Platt also requires this many DISTINCT graded days before it is
# trustworthy: the row-count gate alone is opened by a single large slate (e.g.
# 2272 rows from one 06-15 slate), which gives no cross-day CV. A free 2-param
# Platt fit with a 5-fold expanding-window CV needs each validation fold on a
# different day. 10 days (~2 weeks of slates) balances robustness vs reach time.
CALIBRATION_MIN_DAYS = 10


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


def _is_graded_calibration_row(r: dict) -> bool:
    return (
        r.get("run_type") == "calibration"
        and _nonempty(r.get("over_p_raw"))
        and r.get("result") in ("W", "L")
    )


def count_calibration_platt(rows: list[dict]) -> int:
    """Graded calibration rows with over_p_raw (all evaluated prop stats)."""
    return sum(1 for r in rows if _is_graded_calibration_row(r))


def _normalize_calendar_day(raw: str | None) -> str | None:
    """Strict ISO ``YYYY-MM-DD`` -> canonical day string; None if missing/unparseable.

    Keying distinct days on a normalized date (not the raw string) stops producer
    format drift (e.g. '2026-6-15', '06/15/2026') from spawning phantom distinct days
    and mis-opening the Calibration Platt gate. ``date.fromisoformat`` enforces the
    YYYY-MM-DD contract; anything else is treated as drift.
    """
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return None


def count_calibration_days(rows: list[dict]) -> int:
    """Distinct graded days in the calibration log (cross-day CV validity).

    Counts days by normalized ISO date so non-ISO drift cannot inflate the count
    (over-counting would mis-open the gate, deploying a Platt fit on fewer real
    cross-validation days than reported). Unparseable non-empty dates are excluded
    and a single aggregated warning is emitted so producer drift is visible.
    """
    days: set[str] = set()
    drift = 0
    for r in rows:
        if not _is_graded_calibration_row(r):
            continue
        norm = _normalize_calendar_day(r.get("date"))
        if norm is None:
            if _nonempty(r.get("date")):
                drift += 1
            continue
        days.add(norm)
    if drift:
        print(
            f"[gate_check] WARNING: {drift} graded calibration row(s) had a non-ISO "
            f"date (expected YYYY-MM-DD); excluded from the distinct-day count",
            file=sys.stderr,
        )
    return len(days)


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
    """pick_log_custom.csv rows with a real (non-null, non-zero) clv value."""
    count = 0
    for r in rows:
        raw = r.get("clv")
        if not _nonempty(raw):
            continue
        try:
            if float(raw) != 0:
                count += 1
        except (TypeError, ValueError):
            continue
    return count


# ---------------------------------------------------------------------------
# Gate definitions
# ---------------------------------------------------------------------------

GATES = [
    # (label, counter_fn, target, note, secondary)
    # secondary is None or (sec_fn, sec_target, sec_label): the gate is only
    # "reached" when BOTH the primary count and the secondary count meet target.
    #
    # H3 is SUPERSEDED: its sample (carded primary/bonus over_p_raw) is ~90%
    # one-directional (65 under / 7 over) so it cannot fit a both-sided
    # over_p->P(win) curve. Use Calibration Platt (unbiased, both directions)
    # as the deploy basis instead. H3 left here for historical visibility only.
    ("H3 Platt refit",     count_h3_platt,      100, "SUPERSEDED (carded sample ~90% one-directional) -> use Calibration Platt", None),
    ("MLB Platt refit",    count_mlb_platt,      100, "graded MLB over_p_raw rows", None),
    ("EdgeModel CLV",      count_edgemodel_clv,  100, "CLV rows in pick_log_custom.csv", None),
    # WNBA go-live gate CLOSED 2026-06-09 — went live at 98/100 (user-approved).
    ("SGP Platt calib",    count_sgp_platt,      100, "scored SGP slips", None),
    ("Combo Platt calib",  count_combo_platt,    100, "scored RA/PRA/PR/PA picks", None),
    ("Calibration Platt",  count_calibration_platt, 100, "graded calibration rows (all evaluated props)",
     (count_calibration_days, CALIBRATION_MIN_DAYS, "distinct days")),
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _status(count: int, target: int, reached: bool) -> str:
    if reached:
        return "*** REACHED — ready to act ***"
    if count >= target:
        # Primary count met but a secondary requirement (see note) still blocks.
        return "primary met — blocked (see note)"
    pct = count / target * 100
    bar = int(pct / 5)  # 20-char wide bar
    return f"[{'#' * bar}{'.' * (20 - bar)}] {pct:5.1f}%"


def compute_gate_status() -> list[tuple]:
    """Compute ``(label, count, target, note, reached)`` for every open gate.

    Shared by ``main()`` (the CLI table) and ``gate_digest.py`` (the weekly
    digest's data-gate snapshot) so both render from one source of truth. Reads
    the three logs once and routes each row-set to its counter via ``GATES``.
    """
    main_rows   = _read_csv(PICK_LOG)
    custom_rows = _read_csv(PICK_LOG_CUSTOM)
    calibration_rows = _read_csv(PICK_LOG_CALIBRATION)

    # Route the right row-set to each gate counter
    row_map = {
        count_h3_platt:     main_rows,
        count_mlb_platt:    main_rows,
        count_sgp_platt:    main_rows,
        count_combo_platt:  main_rows,
        count_edgemodel_clv: custom_rows,
        count_calibration_platt: calibration_rows,
        count_calibration_days:  calibration_rows,
    }

    results = []
    for label, fn, target, note, secondary in GATES:
        count = fn(row_map[fn])
        if secondary is not None:
            sec_fn, sec_target, sec_label = secondary
            sec_count = sec_fn(row_map[sec_fn])
            note = f"{note} | {sec_label} {sec_count}/{sec_target}"
            reached = count >= target and sec_count >= sec_target
        else:
            reached = count >= target
        results.append((label, count, target, note, reached))
    return results


def main() -> None:
    results = compute_gate_status()

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

    for label, count, target, note, reached in results:
        status = _status(count, target, reached)
        marker = "*" if reached else " "
        print(
            f"  {marker} {label:<{w_label}} {count:>{w_count}} {target:>{w_target}}  "
            f"{status:<{w_status}}  {note}"
        )

    print(f"  {sep}")
    open_count = sum(1 for r in results if r[4])
    total = len(results)
    print(f"  {open_count}/{total} gates reached\n")


if __name__ == "__main__":
    main()
