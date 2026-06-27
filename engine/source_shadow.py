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
import math
import sys
from collections import defaultdict
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

import edgemodel_adapter as ea
from name_utils import name_key
from prob_core import calc_prop_prob
from crps import crps_normal

try:
    from calibrated import SIGMA, SIGMA_WNBA, NB_R
except Exception:  # pragma: no cover
    SIGMA, SIGMA_WNBA, NB_R = {}, {}, {}

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
    # #11 CRPS: full-distribution proper score vs the realized stat VALUE (when known).
    # Blank unless an actuals map supplies the realized value for the (player, stat).
    "actual_value", "live_crps", "em_crps",
]


def _predictive_sigma(stat: str, sport: str, mu: float) -> float:
    """Moment-matched Normal sigma for a source's predictive at mean `mu`, mirroring the
    pricing distribution family: Normal-SIGMA stats use sigma=max(mu*mult,min); NB stats
    use sigma=sqrt(mu + mu^2/r); else a Poisson-ish sqrt(mu). Both sources use this so
    CRPS differences isolate projection (mean) quality."""
    table = SIGMA_WNBA if (sport or "").upper() == "WNBA" else SIGMA
    spec = table.get(stat) or SIGMA.get(stat)
    if isinstance(spec, dict):
        return max(abs(mu) * spec.get("mult", 0.35), spec.get("min", 1.0))
    r = NB_R.get(stat)
    if r:
        return math.sqrt(max(abs(mu) + mu * mu / r, 1e-9))
    return max(math.sqrt(max(abs(mu), 1e-9)), 1.0)


def _crps_pair(live_proj, em_proj, stat, sport, actual_value):
    """(live_crps, em_crps) vs the realized value; ('' , '') when no actual is known."""
    if actual_value is None:
        return "", ""
    try:
        lc = crps_normal(live_proj, _predictive_sigma(stat, sport, live_proj), actual_value)
        ec = crps_normal(em_proj, _predictive_sigma(stat, sport, em_proj), actual_value)
        return round(lc, 6), round(ec, 6)
    except Exception:
        return "", ""


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


def compare_rows(pick_rows: list[dict], adapter_fetch=ea.fetch, db_path=None,
                 actuals: dict = None) -> list[dict]:
    """Join graded pick rows to EdgeModel projections; return comparison rows.

    pick_rows: dicts with date/sport/player/stat/line/direction/proj/result (pick_log).
    adapter_fetch: injectable for tests. Only rows that are graded (result in W/L),
    have a numeric line, and have an EdgeModel projection for that (player, stat)
    are compared; everything else is skipped.

    actuals: optional {(date, name_key, STAT): realized_value} -> enables the #11 CRPS
    columns (full-distribution proper score vs the realized stat value). When absent the
    CRPS columns are blank (the over/under Brier still scores from the binary outcome).
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
            actual_value = actuals.get((date, nk, stat)) if actuals else None
            lc, ec = _crps_pair(live_proj, em_proj, stat, sport, actual_value)
            out.append({
                "date": date, "sport": sport, "player": r.get("player", ""),
                "stat": stat, "line": line, "live_proj": live_proj, "em_proj": em_proj,
                "live_side": live_side, "em_side": em_side, "actual_over": int(actual_over),
                "live_win": int(live_win), "em_win": int(em_win), "agree": int(agree),
                "disagree_winner": disagree_winner,
                "live_prob_over": lp, "em_prob_over": ep, "live_brier": lb, "em_brier": eb,
                "actual_value": "" if actual_value is None else actual_value,
                "live_crps": lc, "em_crps": ec,
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


_ACTUALS_PATH = Path(DATA_DIR) / "graded_actuals.csv"


def _read_actuals(path: Path = None) -> dict:
    """Optional {(date, name_key, STAT): value} from data/graded_actuals.csv (cols
    date, player, stat, actual). Absent -> {} (CRPS columns stay blank). This is the
    feed that activates #11 in production -- a grade-time writer drops realized stat
    values here; until then CRPS is computable on demand via compare_rows(actuals=...)."""
    p = Path(path or _ACTUALS_PATH)
    if not p.exists():
        return {}
    out: dict = {}
    try:
        with open(p, "r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    val = float(r.get("actual"))
                except (TypeError, ValueError):
                    continue
                out[((r.get("date") or "").strip(), name_key(r.get("player", "")),
                     (r.get("stat") or "").strip().upper())] = val
    except OSError:
        return {}
    return out


def run(date: str | None = None, pick_log_path: Path = None, db_path=None,
        out_path: Path = None, actuals: dict = None) -> list[dict]:
    rows = _read_pick_log(Path(pick_log_path or PICK_LOG_PATH), date)
    comp = compare_rows(rows, db_path=db_path, actuals=actuals if actuals is not None else _read_actuals())
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
