"""source_readiness.py -- per-(sport,market) readiness verdict + coverage_manifest.

Aggregates data/pick_log_source_compare.csv (from source_shadow.py) into a
per-(sport, market) verdict: is EdgeModel ready to take this market over from the
live source? The gate that will eventually drive a per-market handover.

Signal = head-to-head on DISAGREEMENTS only (when both sources pick the same side
the pick carries no comparative information). Two preconditions before a market can
leave 'shadow':
  1. MIN-SAMPLE: at least MIN_DISAGREE graded disagreements (agreements don't count).
  2. EDGE: EdgeModel's win-rate-on-disagreements is significantly > 50% (normal-approx
     lower bound clears 0.5), i.e. not just noise.

Read-only over the comparison CSV; writes data/coverage_manifest.csv. The manifest
is the resolver's eventual input; today every market is 'shadow' (EdgeModel logged,
live source priced) until the data clears the gate. Run after source_shadow.py.

NOTE: this scores DIRECTION agreement. The stronger gate (proper scoring: Brier/ECE
on each source's probabilities, + CLV) needs both sources' probabilities logged --
a later upgrade once source_shadow prices the challenger through pricing_core.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from datetime import date as _date
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

try:
    from paths import DATA_DIR
except Exception:  # pragma: no cover
    DATA_DIR = _ENGINE.parent / "data"

_COMPARE_PATH = Path(DATA_DIR) / "pick_log_source_compare.csv"
_MANIFEST_PATH = Path(DATA_DIR) / "coverage_manifest.csv"

MIN_DISAGREE = 30          # min-sample precondition (disagreements, not total picks)
_Z = 1.96                  # ~95% one-sided-ish normal-approx margin

# Walk-forward purged/embargoed evaluation (#10, López de Prado). The pooled win-rate
# can be carried by one hot streak; this scores EdgeModel's disagreement win-rate
# out-of-sample across contiguous time folds, purging rows within EMBARGO_DAYS of each
# fold boundary. Advisory + a veto: a market can't be ready-candidate if it clears the
# pooled gate but FAILS out-of-sample. Non-blocking when too little dated data exists.
WF_FOLDS = 5
WF_EMBARGO_DAYS = 1

_MANIFEST_FIELDS = [
    "sport", "market", "live_source", "challenger", "mode", "weight",
    "n_total", "n_disagree", "em_win_rate_dis", "min_sample_ok", "edge_ok",
    "em_brier_mean", "live_brier_mean", "brier_edge",
    "wf_win_rate", "wf_folds", "wf_ok", "verdict", "target_weight",
]


def _parse_date(s):
    try:
        y, m, d = str(s)[:10].split("-")
        return _date(int(y), int(m), int(d))
    except Exception:
        return None


def _walk_forward(dis_rows: list, n_folds: int = WF_FOLDS,
                  embargo_days: int = WF_EMBARGO_DAYS):
    """Out-of-sample EdgeModel disagreement win-rate across contiguous time folds.

    dis_rows: [(date_str, em_won_bool)] for DISAGREEMENTS only. Splits the distinct
    dates into n_folds contiguous blocks; within each block (after the first) purges
    rows inside the first `embargo_days` after the block boundary. Returns
    (mean_fold_win_rate, n_folds_used), or (None, 0) when too little dated data exists
    to evaluate (then the caller treats it as non-blocking).
    """
    dated = [(_parse_date(d), bool(w)) for (d, w) in dis_rows]
    dated = [(d, w) for (d, w) in dated if d is not None]
    uniq = sorted({d for d, _ in dated})
    if len(dated) < n_folds * 2 or len(uniq) < n_folds:
        return None, 0
    fold_size = math.ceil(len(uniq) / n_folds)
    rates = []
    for k in range(n_folds):
        block = uniq[k * fold_size:(k + 1) * fold_size]
        if not block:
            continue
        start = block[0]
        block_set = set(block)
        kept = [w for (d, w) in dated
                if d in block_set and (k == 0 or (d - start).days >= embargo_days)]
        if kept:
            rates.append(sum(kept) / len(kept))
    if not rates:
        return None, 0
    return sum(rates) / len(rates), len(rates)

# Weight-ramp (advisory): shrunk-toward-incumbent, capped during maturation. The
# manifest's LIVE `weight` stays 0 (resolver dormant) until promote() is run for a
# market -- a deliberate, reversible sign-off, never automatic.
RAMP_W_MAX = 0.5            # cap: never auto-recommend full handover while maturing
RAMP_Z0, RAMP_Z1 = 0.5, 0.65   # win-rate Wilson-LB ramp band -> [0, W_MAX]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _wilson_lower(wins: int, n: int, z: float = _Z) -> float:
    """Wilson score lower bound for a binomial proportion (0 if n==0)."""
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - margin) / denom


def score(rows: list[dict]) -> list[dict]:
    """Aggregate compare rows -> per-(sport, market) readiness manifest rows."""
    agg: dict = defaultdict(lambda: {"n": 0, "dis": 0, "em": 0, "eb": 0.0, "lb": 0.0, "bn": 0})
    dis_by_market: dict = defaultdict(list)   # (sport,market) -> [(date, em_won)] for #10
    for r in rows:
        key = ((r.get("sport") or "").upper(), (r.get("stat") or "").upper())
        a = agg[key]
        a["n"] += 1
        if str(r.get("agree")) == "0":
            a["dis"] += 1
            em_won = r.get("disagree_winner") == "edgemodel"
            if em_won:
                a["em"] += 1
            dis_by_market[key].append((r.get("date"), em_won))
        eb, lb = _f(r.get("em_brier")), _f(r.get("live_brier"))
        if eb is not None and lb is not None:
            a["eb"] += eb
            a["lb"] += lb
            a["bn"] += 1

    out: list[dict] = []
    for (sport, market), a in sorted(agg.items()):
        n, dis, em = a["n"], a["dis"], a["em"]
        win_rate = em / dis if dis else 0.0
        min_sample_ok = dis >= MIN_DISAGREE
        edge_ok = _wilson_lower(em, dis) > 0.5            # EdgeModel beats 50% with confidence
        # Proper-scoring veto: lower Brier = better. brier_edge>0 => EdgeModel scores better.
        em_brier = a["eb"] / a["bn"] if a["bn"] else None
        live_brier = a["lb"] / a["bn"] if a["bn"] else None
        brier_edge = (live_brier - em_brier) if a["bn"] else None
        brier_ok = brier_edge is None or brier_edge >= 0  # absent brier doesn't block; worse Brier vetoes
        # #10 walk-forward purged/embargoed out-of-sample win-rate. Non-blocking when
        # too little dated data exists (wf None -> wf_ok True); a veto otherwise.
        wf_win_rate, wf_folds = _walk_forward(dis_by_market.get((sport, market), []))
        wf_ok = wf_win_rate is None or wf_win_rate > 0.5
        if min_sample_ok and edge_ok and brier_ok and wf_ok:
            verdict, mode = "ready-candidate", "shadow"   # promotion is a separate, manual gate
        elif not min_sample_ok:
            verdict, mode = "insufficient-sample", "shadow"
        else:
            verdict, mode = "live-source-holds", "shadow"
        # Advisory ramp: what weight you COULD promote to. Live weight stays 0.
        lb = _wilson_lower(em, dis)
        ramp_frac = max(0.0, min(1.0, (lb - RAMP_Z0) / (RAMP_Z1 - RAMP_Z0)))
        target_weight = round(RAMP_W_MAX * ramp_frac, 3) if verdict == "ready-candidate" else 0.0
        out.append({
            "sport": sport, "market": market, "live_source": "sabersim",
            "challenger": "edgemodel", "mode": mode, "weight": 0.0,
            "n_total": n, "n_disagree": dis, "em_win_rate_dis": round(win_rate, 3),
            "min_sample_ok": int(min_sample_ok), "edge_ok": int(edge_ok),
            "em_brier_mean": round(em_brier, 4) if em_brier is not None else "",
            "live_brier_mean": round(live_brier, 4) if live_brier is not None else "",
            "brier_edge": round(brier_edge, 4) if brier_edge is not None else "",
            "wf_win_rate": round(wf_win_rate, 3) if wf_win_rate is not None else "",
            "wf_folds": wf_folds, "wf_ok": int(wf_ok),
            "verdict": verdict, "target_weight": target_weight,
        })
    return out


def _rewrite_market(sport: str, market: str, *, mode: str, weight: float,
                    manifest_path=None) -> bool:
    """Set the LIVE mode+weight for one (sport, market) in the manifest. Returns True if found."""
    path = Path(manifest_path or _MANIFEST_PATH)
    if not path.exists():
        return False
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys()) if rows else _MANIFEST_FIELDS
    hit = False
    for r in rows:
        if (r.get("sport") or "").upper() == sport.upper() and (r.get("market") or "").upper() == market.upper():
            r["mode"], r["weight"], hit = mode, weight, True
    if hit:
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return hit


def promote(sport: str, market: str, weight: float = None, manifest_path=None) -> bool:
    """DELIBERATE handover: set a market live for EdgeModel (mode=blend, weight>0).

    Defaults to the market's advisory target_weight. The resolver then blends
    EdgeModel into that market on the next run. Reversible via demote(). This is the
    sign-off step -- nothing promotes automatically.
    """
    path = Path(manifest_path or _MANIFEST_PATH)
    if weight is None and path.exists():
        with open(path, "r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("sport") or "").upper() == sport.upper() and \
                   (r.get("market") or "").upper() == market.upper():
                    weight = _f(r.get("target_weight")) or 0.0
                    break
    weight = max(0.0, min(1.0, weight or 0.0))
    if weight <= 0.0:
        return False  # nothing to promote (no recommended weight)
    return _rewrite_market(sport, market, mode="blend", weight=weight, manifest_path=manifest_path)


def demote(sport: str, market: str, manifest_path=None) -> bool:
    """ROLLBACK a market to the live source (mode=shadow, weight=0)."""
    return _rewrite_market(sport, market, mode="shadow", weight=0.0, manifest_path=manifest_path)


def _read_compare(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


_GL_COMPARE_PATH = Path(DATA_DIR) / "pick_log_gl_source_compare.csv"


def run(compare_path: Path = None, manifest_path: Path = None,
        gl_compare_path: Path = None) -> list[dict]:
    rows = _read_compare(Path(compare_path or _COMPARE_PATH))
    # Also ingest the MLB game-line comparison (sport=MLB, market -> stat). #9: now
    # carries each source's Brier, so the proper-scoring veto applies here too.
    for r in _read_compare(Path(gl_compare_path or _GL_COMPARE_PATH)):
        rows.append({"sport": "MLB", "stat": (r.get("market") or "").upper(),
                     "agree": r.get("agree"), "disagree_winner": r.get("disagree_winner"),
                     "em_brier": r.get("em_brier"), "live_brier": r.get("live_brier")})
    manifest = score(rows)
    out = Path(manifest_path or _MANIFEST_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(manifest)
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Per-market EdgeModel readiness gate")
    ap.add_argument("--compare", help="path to pick_log_source_compare.csv")
    ns = ap.parse_args()
    man = run(compare_path=ns.compare)
    print(f"\nReadiness manifest ({len(man)} markets) -> {_MANIFEST_PATH}")
    print(f"{'sport/market':18} {'n':>5} {'disagr':>7} {'EM win%':>8} {'verdict':>20}")
    for m in man:
        print(f"{m['sport']+'/'+m['market']:18} {m['n_total']:>5} {m['n_disagree']:>7} "
              f"{100*m['em_win_rate_dis']:>7.1f}% {m['verdict']:>20}")
    print(f"\nMIN_DISAGREE={MIN_DISAGREE}. Every market stays 'shadow' until it clears the "
          f"sample + edge gate; promotion to 'live' is a separate, deliberate step.")
