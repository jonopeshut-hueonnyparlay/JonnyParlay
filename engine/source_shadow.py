"""source_shadow.py -- champion/challenger source comparison (EdgeModel vs live).

Post-hoc, read-only, NO live-path change. For graded prop picks in pick_log.csv
(the live / champion source), look up EdgeModel's projection
(edgemodel_adapter -> projections.db) for the same (player, stat, date), derive
the actual over/under outcome from the logged (direction, result), and record
both sources' implied side + who the outcome favoured.

The signal that matters for a readiness-gated handover: when the two sources
DISAGREE on the side, the market outcome tells you which source was right. (When
they agree, the pick carries no comparative information.)

Writes data/pick_log_source_compare.csv -- a NEW analysis artifact; it does NOT
touch the pick_log schema. Run after grading:
    python engine/source_shadow.py [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

import edgemodel_adapter as ea
from name_utils import name_key
from prob_core import calc_prop_prob

try:
    from paths import PICK_LOG_PATH, DATA_DIR
except Exception:  # pragma: no cover - fallback if paths import differs
    DATA_DIR = _ENGINE.parent / "data"
    PICK_LOG_PATH = DATA_DIR / "pick_log.csv"

_OUT_PATH = Path(DATA_DIR) / "pick_log_source_compare.csv"
_OUT_FIELDS = [
    "date", "sport", "player", "stat", "line",
    "live_proj", "em_proj", "live_side", "em_side", "actual_over",
    "live_win", "em_win", "agree", "disagree_winner",
    # Proper scoring: price BOTH sources through the same engine (pricing held
    # constant -> isolates projection quality), Brier vs the realized over/under.
    "live_prob_over", "em_prob_over", "live_brier", "em_brier",
]


def _brier_pair(live_proj, em_proj, line, stat, sport, actual_over):
    """Over-probability + Brier for each source via calc_prop_prob. ('' x4) on failure."""
    try:
        live_p = calc_prop_prob(live_proj, line, stat, sport=sport)[0]
        em_p = calc_prop_prob(em_proj, line, stat, sport=sport)[0]
        return (round(live_p, 6), round(em_p, 6),
                round((live_p - actual_over) ** 2, 6), round((em_p - actual_over) ** 2, 6))
    except Exception:
        return "", "", "", ""


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def compare_rows(pick_rows: list[dict], adapter_fetch=ea.fetch, db_path=None) -> list[dict]:
    """Join graded pick rows to EdgeModel projections; return comparison rows.

    pick_rows: dicts with date/sport/player/stat/line/direction/proj/result (pick_log).
    adapter_fetch: injectable for tests. Only rows that are graded (result in W/L),
    have a numeric line, and have an EdgeModel projection for that (player, stat)
    are compared; everything else is skipped.
    """
    # group rows by (sport, date) so the adapter is queried once per slate
    by_slate: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in pick_rows:
        sport = (r.get("sport") or "").upper()
        date = r.get("date") or ""
        if sport and date:
            by_slate[(sport, date)].append(r)

    out: list[dict] = []
    for (sport, date), rows in by_slate.items():
        em = adapter_fetch(sport, date, db_path=db_path)
        if not em:
            continue
        for r in rows:
            result = (r.get("result") or "").strip().upper()
            if result not in ("W", "L"):
                continue
            stat = (r.get("stat") or "").strip().upper()
            line = _f(r.get("line"))
            live_proj = _f(r.get("proj"))
            direction = (r.get("direction") or "").strip().lower()
            if line is None or direction not in ("over", "under"):
                continue
            nk = name_key(r.get("player"))
            em_proj = em.get((nk, stat))
            if em_proj is None:
                continue

            # actual over/under outcome, derived from the live bet's (side, result)
            actual_over = (direction == "over") == (result == "W")
            live_side = direction
            em_side = "over" if em_proj > line else "under"
            live_win = result == "W"
            em_win = (em_side == "over") == actual_over
            agree = live_side == em_side
            disagree_winner = "" if agree else ("edgemodel" if em_win else "live")

            lp, ep, lb, eb = _brier_pair(live_proj, em_proj, line, stat, sport, actual_over)
            out.append({
                "date": date, "sport": sport, "player": r.get("player", ""),
                "stat": stat, "line": line, "live_proj": live_proj, "em_proj": em_proj,
                "live_side": live_side, "em_side": em_side, "actual_over": int(actual_over),
                "live_win": int(live_win), "em_win": int(em_win), "agree": int(agree),
                "disagree_winner": disagree_winner,
                "live_prob_over": lp, "em_prob_over": ep, "live_brier": lb, "em_brier": eb,
            })
    return out


def summarize(rows: list[dict]) -> dict:
    """Per (sport, stat) and overall: counts + on-disagreement win rates."""
    agg: dict = defaultdict(lambda: {"n": 0, "agree": 0, "disagree": 0,
                                     "em_win_dis": 0, "live_win_dis": 0})
    for r in rows:
        for key in ((r["sport"], r["stat"]), ("ALL", "ALL")):
            a = agg[key]
            a["n"] += 1
            if r["agree"]:
                a["agree"] += 1
            else:
                a["disagree"] += 1
                a["em_win_dis"] += 1 if r["disagree_winner"] == "edgemodel" else 0
                a["live_win_dis"] += 1 if r["disagree_winner"] == "live" else 0
    return agg


def _read_pick_log(path: Path, date: str | None) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if not date or (r.get("date") == date)]


def run(date: str | None = None, pick_log_path: Path = None, db_path=None,
        out_path: Path = None) -> list[dict]:
    rows = _read_pick_log(Path(pick_log_path or PICK_LOG_PATH), date)
    comp = compare_rows(rows, db_path=db_path)
    out = Path(out_path or _OUT_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_OUT_FIELDS)
        w.writeheader()
        w.writerows(comp)
    return comp


def _print_summary(rows: list[dict]) -> None:
    agg = summarize(rows)
    print(f"\nSource comparison: {len(rows)} graded prop picks with an EdgeModel projection")
    print(f"{'sport/stat':18} {'n':>5} {'agree%':>7} {'disagr':>7} "
          f"{'EM win%(dis)':>13} {'live win%(dis)':>14}")
    for key in sorted(agg, key=lambda k: (k != ('ALL', 'ALL'), k)):
        a = agg[key]
        dis = a["disagree"] or 1
        label = f"{key[0]}/{key[1]}"
        print(f"{label:18} {a['n']:>5} {100*a['agree']/(a['n'] or 1):>6.1f}% "
              f"{a['disagree']:>7} {100*a['em_win_dis']/dis:>12.1f}% "
              f"{100*a['live_win_dis']/dis:>13.1f}%")
    print("\nRead: on DISAGREEMENTS, the higher 'win%(dis)' source projected the better side.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="EdgeModel-vs-live source comparison shadow")
    ap.add_argument("--date", help="limit to one pick_log date (YYYY-MM-DD)")
    ns = ap.parse_args()
    comp = run(ns.date)
    print(f"wrote {len(comp)} comparison rows -> {_OUT_PATH}")
    _print_summary(comp)
